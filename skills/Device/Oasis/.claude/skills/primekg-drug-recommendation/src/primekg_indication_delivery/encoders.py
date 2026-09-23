from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem


RDLogger.DisableLog("rdApp.*")


def smiles_to_fingerprint(smiles: str, radius: int, n_bits: int) -> np.ndarray:
    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        return np.zeros(n_bits, dtype=np.float32)
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
    array = np.zeros(n_bits, dtype=np.float32)
    DataStructs.ConvertToNumpyArray(fp, array)
    return array


def _hash_token(token: str, width: int) -> tuple[int, float]:
    digest = hashlib.md5(token.encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % width
    sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
    return index, sign


class DiseaseEncoder:
    def __init__(self, embed_dim: int = 256) -> None:
        self.embed_dim = int(embed_dim)
        self._disease_to_tokens: dict[str, list[str]] = {}

    def fit(
        self,
        disease_protein_edges: pd.DataFrame,
        disease_phenotype_edges: pd.DataFrame,
    ) -> "DiseaseEncoder":
        disease_to_tokens: dict[str, list[str]] = {}
        if not disease_protein_edges.empty:
            for disease_id, protein_id in disease_protein_edges[["disease_id", "protein_id"]].itertuples(index=False):
                disease_to_tokens.setdefault(str(disease_id), []).append(f"disease_protein::{protein_id}")
        if not disease_phenotype_edges.empty:
            for disease_id, phenotype_id in disease_phenotype_edges[["disease_id", "phenotype_id"]].itertuples(
                index=False
            ):
                disease_to_tokens.setdefault(str(disease_id), []).append(f"disease_phenotype::{phenotype_id}")
        self._disease_to_tokens = disease_to_tokens
        return self

    def has_disease(self, disease_id: str) -> bool:
        return str(disease_id) in self._disease_to_tokens

    def transform(self, disease_ids: pd.Series | list[str]) -> np.ndarray:
        disease_values = [str(value) for value in disease_ids]
        if not disease_values:
            return np.zeros((0, self.embed_dim), dtype=np.float32)
        matrix = np.zeros((len(disease_values), self.embed_dim), dtype=np.float32)
        for row_idx, disease_id in enumerate(disease_values):
            tokens = self._disease_to_tokens.get(disease_id, [])
            for token in tokens:
                index, sign = _hash_token(token, self.embed_dim)
                matrix[row_idx, index] += sign
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return (matrix / norms).astype(np.float32)

    def export_state(self) -> dict:
        return {
            "embed_dim": self.embed_dim,
            "disease_to_tokens": dict(self._disease_to_tokens),
        }

    @classmethod
    def from_state(cls, payload: dict) -> "DiseaseEncoder":
        encoder = cls(embed_dim=payload["embed_dim"])
        encoder._disease_to_tokens = {
            str(disease_id): [str(token) for token in tokens]
            for disease_id, tokens in payload["disease_to_tokens"].items()
        }
        return encoder


class DrugEncoder:
    def __init__(
        self,
        embed_dim: int = 256,
        radius: int = 2,
        n_bits: int = 2048,
        seed: int = 42,
    ) -> None:
        self.embed_dim = int(embed_dim)
        self.radius = int(radius)
        self.n_bits = int(n_bits)
        self.seed = int(seed)
        self._projection: np.ndarray | None = None
        self._drug_to_proteins: dict[str, list[str]] = {}
        self._cached_embeddings: dict[str, np.ndarray] = {}

    def fit(
        self,
        candidate_pool: pd.DataFrame,
        drug_protein_edges: pd.DataFrame | None = None,
    ) -> "DrugEncoder":
        rng = np.random.default_rng(self.seed)
        self._projection = rng.normal(
            loc=0.0,
            scale=1.0 / np.sqrt(self.n_bits),
            size=(self.n_bits, self.embed_dim),
        ).astype(np.float32)
        if drug_protein_edges is not None and not drug_protein_edges.empty:
            grouped = drug_protein_edges.groupby("drugbank_id")["protein_id"].apply(list)
            self._drug_to_proteins = {str(key): [str(value) for value in values] for key, values in grouped.items()}
        else:
            self._drug_to_proteins = {}
        if candidate_pool.empty:
            self._cached_embeddings = {}
            return self
        candidate_embeddings = self._encode_uncached(candidate_pool[["drugbank_id", "smiles"]])
        self._cached_embeddings = {
            str(drug_id): candidate_embeddings[row_idx]
            for row_idx, drug_id in enumerate(candidate_pool["drugbank_id"].tolist())
        }
        return self

    def _protein_hash_embedding(self, drugbank_id: str) -> np.ndarray:
        vector = np.zeros(self.embed_dim, dtype=np.float32)
        proteins = self._drug_to_proteins.get(str(drugbank_id), [])
        if not proteins:
            return vector
        for protein_id in proteins:
            index, sign = _hash_token(f"drug_protein::{protein_id}", self.embed_dim)
            vector[index] += sign
        norm = np.linalg.norm(vector)
        return vector if norm == 0.0 else vector / norm

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        if self._projection is None:
            raise ValueError("DrugEncoder must be fit before transform.")
        if df.empty:
            return np.zeros((0, self.embed_dim), dtype=np.float32)
        rows: list[np.ndarray] = []
        uncached_rows: list[tuple[int, str, str]] = []
        for row_idx, (drug_id, smiles) in enumerate(df[["drugbank_id", "smiles"]].itertuples(index=False)):
            cached = self._cached_embeddings.get(str(drug_id))
            if cached is not None:
                rows.append(cached)
            else:
                rows.append(np.zeros(self.embed_dim, dtype=np.float32))
                uncached_rows.append((row_idx, str(drug_id), str(smiles)))
        if uncached_rows:
            uncached_df = pd.DataFrame(uncached_rows, columns=["row_idx", "drugbank_id", "smiles"])
            uncached_embeddings = self._encode_uncached(uncached_df[["drugbank_id", "smiles"]])
            for embed_idx, row_idx in enumerate(uncached_df["row_idx"].tolist()):
                rows[row_idx] = uncached_embeddings[embed_idx]
        return np.vstack(rows).astype(np.float32)

    def _encode_uncached(self, df: pd.DataFrame) -> np.ndarray:
        if self._projection is None:
            raise ValueError("DrugEncoder must be fit before encoding.")
        fingerprints = np.vstack(
            [smiles_to_fingerprint(smiles, radius=self.radius, n_bits=self.n_bits) for smiles in df["smiles"]]
        ).astype(np.float32)
        fingerprint_embeddings = fingerprints @ self._projection
        protein_embeddings = np.vstack(
            [self._protein_hash_embedding(str(drug_id)) for drug_id in df["drugbank_id"]]
        ).astype(np.float32)
        embeddings = 0.8 * fingerprint_embeddings + 0.2 * protein_embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return (embeddings / norms).astype(np.float32)

    def export_state(self) -> dict:
        return {
            "embed_dim": self.embed_dim,
            "radius": self.radius,
            "n_bits": self.n_bits,
            "seed": self.seed,
            "projection": None if self._projection is None else self._projection.copy(),
            "drug_to_proteins": dict(self._drug_to_proteins),
            "cached_embeddings": {
                str(drug_id): embedding.copy() for drug_id, embedding in self._cached_embeddings.items()
            },
        }

    @classmethod
    def from_state(cls, payload: dict) -> "DrugEncoder":
        encoder = cls(
            embed_dim=payload["embed_dim"],
            radius=payload["radius"],
            n_bits=payload["n_bits"],
            seed=payload["seed"],
        )
        projection = payload.get("projection")
        encoder._projection = None if projection is None else np.asarray(projection, dtype=np.float32)
        encoder._drug_to_proteins = {
            str(drug_id): [str(protein_id) for protein_id in proteins]
            for drug_id, proteins in payload["drug_to_proteins"].items()
        }
        encoder._cached_embeddings = {
            str(drug_id): np.asarray(embedding, dtype=np.float32)
            for drug_id, embedding in payload["cached_embeddings"].items()
        }
        return encoder

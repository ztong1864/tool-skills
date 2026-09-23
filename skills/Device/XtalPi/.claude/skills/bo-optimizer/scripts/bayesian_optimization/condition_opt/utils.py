import pandas as pd
from pathlib import Path
from rdkit import Chem

from summit.domain import CategoricalVariable, ContinuousVariable
from summit import Domain
from summit.utils.dataset import DataSet

def canonicalize_smiles(smiles):
    if smiles == "blanck_cell":
        return smiles
    try:
        return Chem.MolToSmiles(Chem.MolFromSmiles(smiles))
    except:
        return smiles


def get_reaction_space(domain, desc_class, reagent_types):
    """Get reaction space from descriptor csv file"""
    desc_dict = desc_class.get_desc_df()
    for tp in reagent_types:
        smiles_list = desc_dict[tp].index.tolist()
        descriptor_list = DataSet.from_df(desc_dict[tp])
        domain += CategoricalVariable(name=tp, description=tp, levels=smiles_list, descriptors=descriptor_list)

    return domain


def get_target_value(domain):
    """Get target value by index"""
    domain += ContinuousVariable(name="yld", description="yld", bounds=[0, 100], is_objective=True, maximize=True)
    #domain += ContinuousVariable(name="ee", description="ee", bounds=[-100, 100], is_objective=True, maximize=True)

    return domain



# descriptor mapping
from pathlib import Path
import pandas as pd

# 假设 canonicalize_smiles 已经在别处定义
# from utils import canonicalize_smiles


class descClass:
    def __init__(self, desc_path: Path):
        """一次性读入 5 个类别的描述文件"""
        # 1. 读入 CSV
        self.tempo_desc      = pd.read_csv(desc_path / "tempo_desc_datadf.csv",      index_col=0)
        self.additive_desc   = pd.read_csv(desc_path / "additive_desc_datadf.csv",   index_col=0)
        self.ratio_desc      = pd.read_csv(desc_path / "ratio_desc_datadf.csv",      index_col=0)
        self.solvent_desc    = pd.read_csv(desc_path / "solvent_desc_datadf.csv",    index_col=0)
        self.volume_desc     = pd.read_csv(desc_path / "volume_desc_datadf.csv",     index_col=0)
        # self.temperature_desc= pd.read_csv(desc_path / "temperature_desc_datadf.csv",index_col=0)

        # 2. 统一把索引变成 canonical SMILES
        #for attr in ("tempo", "additive", "solvent"):  
            #df = getattr(self, f"{attr}_desc")
            #df.index = df.index.map(canonicalize_smiles)
            #setattr(self, f"{attr}_desc", df)

        # 3. 计算组合空间大小
        space_size = 1
        space_size *= self.tempo_desc.shape[0]
        space_size *= self.additive_desc.shape[0]
        space_size *= self.ratio_desc.shape[0]
        space_size *= self.solvent_desc.shape[0]
        space_size *= self.volume_desc.shape[0]
        # space_size *= self.temperature_desc.shape[0]
        print(f"Total Reaction Space Size: {space_size}")

    # ----------------------------------------------------------
    def map_desc(self, mol_type: str, data_df: pd.Series) -> pd.DataFrame:
        """
        根据 mol_type 把 data_df 中的 SMILES 映射到对应描述子 DataFrame
        data_df: Series，index 任意，values 为 SMILES
        返回:   DataFrame，行索引与 data_df 一致，列为描述子
        """
        desc_df = getattr(self, f"{mol_type}_desc")
        desc_list = [desc_df.loc[smiles] for smiles in data_df.values]
        return pd.DataFrame(desc_list, index=data_df.index)

    # ----------------------------------------------------------
    def get_desc_df(self) -> dict:
        """一次性返回 6 个描述子表，方便外部调用"""
        return {
            "tempo"      : self.tempo_desc,
            "additive"   : self.additive_desc,
            "ratio"      : self.ratio_desc,
            "solvent"    : self.solvent_desc,
            "volume"     : self.volume_desc,
            # "temperature": self.temperature_desc,
        }

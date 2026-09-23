from summit import *
from scipy.spatial.distance import cdist
import copy
import gpytorch
import botorch
from gpytorch.kernels import MaternKernel, ScaleKernel
from gpytorch.priors import GammaPrior
from gpytorch.constraints import GreaterThan
from tqdm import tqdm
from botorch.models import SingleTaskGP, MixedSingleTaskGP, ModelListGP
from botorch.optim import optimize_acqf_discrete
from botorch.acquisition.multi_objective.monte_carlo import (
    qExpectedHypervolumeImprovement,
    qNoisyExpectedHypervolumeImprovement,
)
from botorch.utils.multi_objective.box_decompositions import NondominatedPartitioning
from botorch.optim import optimize_acqf_discrete
from botorch.sampling.normal import SobolQMCNormalSampler
from sklearn.preprocessing import MinMaxScaler
try:
    from idaes.core.surrogate.pysmo.sampling import CVTSampling, LatinHypercubeSampling
except ImportError:  # pragma: no cover - compatibility fallback for older idaes-pse
    from idaes.surrogate.pysmo.sampling import CVTSampling, LatinHypercubeSampling
import numpy as np
import random
import torch
import pandas as pd
import sys
from joblib import Parallel, delayed
from .constants import tkwargs
from .utils import model_likelihood
from .pareto import pareto_front_2_dim
from .scaler import StandardScaler
from tqdm import tqdm as tqdm_concat
from botorch.acquisition import ExpectedImprovement, qExpectedImprovement
try:
    from botorch.fit import fit_gpytorch_mll as fit_gpytorch_model
except ImportError:  # pragma: no cover - older botorch compatibility
    from botorch import fit_gpytorch_model
class newEDBO:
    def __init__(
        self,
        domain: Domain,
        sobol_num_samples: int = None,
        seed: int = 1216,
        init_sampling_method: str = "CVT",
    ):
        self.domain = domain
        self.all_combos = self.domain.get_categorical_combinations()
        self.all_combos.index = range(len(self.all_combos))
        if sobol_num_samples is None:
            if len(self.all_combos) > 500000:
                self.sobol_num_samples = 128
            elif len(self.all_combos) > 100000:
                self.sobol_num_samples = 256
            elif len(self.all_combos) > 20000:
                self.sobol_num_samples = 512
            else:
                self.sobol_num_samples = 1024
        else:
            self.sobol_num_samples = sobol_num_samples
        self.seed = seed
        self.init_sampling_method = init_sampling_method
        assert init_sampling_method in ["CVT", "LHS"]

        l_all = len(self.all_combos)
        
        #def chunk_indices(total, n_chunks):
        #    chunk_size = (total + n_chunks - 1) // n_chunks
        #    return [(i * chunk_size, min((i + 1) * chunk_size, total)) for i in range(n_chunks)]

        #def encode_chunk(start, end, show_progress=False):
        #   iterator = range(start, end)
        #    if show_progress:
        #        iterator = tqdm(iterator, desc=f"块 {start}-{end}")
        #    for i in iterator:
        #        test_x_i = []
        #        for v in domain.input_variables:
        #            key_v = self.all_combos.loc[i, v.name].values[0]
        #            encode = list(v.ds.loc[key_v])
        #            test_x_i.extend(encode)
        #        chunk_x.append(test_x_i)
        #    return chunk_x

        #n_jobs = 64  # 可根据实际核心数调整
        #chunks = chunk_indices(l_all, n_jobs)
        #results = Parallel(n_jobs=n_jobs)(delayed(encode_chunk)(start, end, idx==0) for idx, (start, end) in enumerate(chunks))
        # 拼接self.all_x时显示进度条
        all_x = []
        for i in tqdm(range(l_all)):
            test_x_i = []
            for v in domain.input_variables:
                key_v = self.all_combos.loc[i, v.name].values[0]
                encode = list(v.ds.loc[key_v])
                test_x_i.extend(encode)
            all_x.append(test_x_i)
        self.all_x = np.array(all_x).astype(float)
    
    # 递归地把 model & likelihood 全部压到 CPU
    def _force_cpu(self):
        for attr in ('model', 'likelihood'):
            obj = getattr(self, attr, None)
            if obj is not None:
                setattr(self, attr, obj.cpu())
    
    def suggest_experiments(self, prev_res: DataSet = None, batch_size: int = 5):
        return self._suggest_experiments_impl(prev_res, batch_size)

    def suggest_experiments_new(self, prev_res: DataSet = None, batch_size: int = 5, alkali_range=None):
        for attr in ('model', 'likelihood'):
            obj = getattr(self, attr, None)
            if obj is not None:          # 只有实例化过才搬
                state = obj.state_dict()
                for k, v in state.items():
                    if isinstance(v, torch.Tensor):
                        state[k] = v.cpu()
                obj.load_state_dict(state)
        
        if alkali_range is not None:
            valid_combos = self.all_combos[self.all_combos["alkali"].isin(alkali_range)]
            valid_x = self.all_x[self.all_combos["alkali"].isin(alkali_range)].copy()
        else:
            valid_combos = self.all_combos.copy()
            valid_x = self.all_x.copy()
        
        return self._suggest_experiments_impl(prev_res, batch_size, valid_combos, valid_x)

    def _suggest_experiments_impl(self, prev_res=None, batch_size=5,
                              valid_combos=None, valid_x=None):
        # 1. 原初始化
        if valid_combos is None:
            valid_combos = self.all_combos.copy()
        if valid_x is None:
            valid_x = self.all_x.copy()
        if prev_res is None or len(prev_res) == 0:
            return self._initial_sampling(batch_size, valid_combos, valid_x)

        # 2. 原训练数据准备
        domain = self.domain
        col_x = [v.name for v in domain.input_variables]
        col_y = [v.name for v in domain.output_variables]
        num_obj = len(col_y)

        train_y, train_x = self._prepare_training_data(prev_res, domain, col_y, col_x)
        scaler_x, scaler_y = MinMaxScaler(), StandardScaler()
        train_x = scaler_x.fit_transform(train_x)
        train_y = scaler_y.fit_transform(train_y)

        # 3. 单目标 vs 多目标 分支
        test_x = torch.tensor(scaler_x.transform(valid_x), **tkwargs).double()
        if num_obj == 1:
            # ---------- 单目标 ----------
            train_x_tensor = torch.tensor(train_x, **tkwargs).double()
            train_y_tensor = torch.tensor(train_y, **tkwargs).double().view(-1, 1)

            gp = SingleTaskGP(train_X=train_x_tensor, train_Y=train_y_tensor)
            mll = gpytorch.mlls.ExactMarginalLogLikelihood(gp.likelihood, gp)
            fit_gpytorch_model(mll)

            xi = 0                                    # ← 调这里
            acqf = qExpectedImprovement(
                    model=gp,
                    best_f=train_y_tensor.max() + xi)
        else:
            # ---------- 原多目标 ----------
            pareto_y = pareto_front_2_dim(train_y)
            ref_point = scaler_y.transform([np.min(train_y, axis=0)])[0]

            models = []
            for i in range(num_obj):
                train_x_i = torch.tensor(train_x, **tkwargs).double()
                train_y_i = torch.tensor(train_y[:, i:i+1], **tkwargs).double()
                gp_i, likelihood = model_likelihood(train_x=train_x_i,
                                                    train_y=train_y_i)
                models.append(SingleTaskGP(
                    train_X=train_x_i,
                    train_Y=train_y_i,
                    covar_module=gp_i.covar_module,
                    likelihood=likelihood,
                ))
            bigmodel = ModelListGP(*models)

            sampler = SobolQMCNormalSampler(torch.Size([self.sobol_num_samples]),
                                            seed=1145141)
            partitioning = NondominatedPartitioning(
                ref_point=torch.tensor(ref_point).float(),
                Y=torch.tensor(pareto_y).float()
            )
            acqf = qExpectedHypervolumeImprovement(
                model=bigmodel,
                sampler=sampler,
                ref_point=ref_point,
                partitioning=partitioning,
            )

        # 4. 原离散优化 & 索引映射（无需改动）
        prev_comb = prev_res[col_x].copy()
        combos = pd.concat([valid_combos, prev_comb]).reset_index()
        combos = combos.drop_duplicates(keep=False)
        acq_result = optimize_acqf_discrete(
            acq_function=acqf,
            choices=test_x,
            q=batch_size,
            unique=True
        )
        best_samples = acq_result[0].cpu().numpy()
        ans_indexs = [np.argmin(cdist([s], test_x, metric="cityblock"))
                    for s in best_samples]
        return valid_combos.iloc[ans_indexs]

    def _initial_sampling(self, batch_size, valid_combos, valid_x):
        k = batch_size
        if self.init_sampling_method == "LHS":
            random_state = np.random.RandomState(self.seed)
            lhs = LHS(self.domain, random_state=random_state)
            return lhs.suggest_experiments(k)
        else:
            df_sampling = valid_x
            idaes = CVTSampling(df_sampling, number_of_samples=k, sampling_type="selection")
            samples = idaes.sample_points()
            
            init_indexs = []
            for sample in samples:
                d_i = cdist([sample], df_sampling, metric="cityblock")
                a = np.argmin(d_i)
                init_indexs.append(a)
            
            if len(init_indexs) < k:
                rand_choices = k - len(init_indexs)
                others = [i for i in range(len(valid_x)) if i not in init_indexs]
                np.random.seed(self.seed)
                random.seed(self.seed)
                init_indexs.extend(np.random.choice(others, rand_choices))
                init_indexs = sorted(init_indexs)
            
            return valid_combos.iloc[init_indexs].copy()

    def _prepare_training_data(self, prev_res, domain, col_y, col_x):
        train_y = prev_res[col_y].to_numpy().astype(float)
        
        # Adjust objectives based on maximize flag
        for i, v in enumerate(domain.output_variables):
            if not v.maximize:
                train_y[:, i] = -train_y[:, i]
        
        # Prepare input features
        train_x = []
        len_prev = len(prev_res)
        for i in range(len_prev):
            now_x = []
            for v in domain.input_variables:
                key_v = prev_res.loc[i, v.name].values[0]
                encode = list(v.ds.loc[key_v])
                now_x.extend(encode)
            train_x.append(now_x)
        
        return train_y, np.array(train_x).astype(float)

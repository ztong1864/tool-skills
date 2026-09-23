from botorch.acquisition import ExpectedImprovement   # 新增 1 行

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
        botorch.fit_gpytorch_model(mll)

        acqf = ExpectedImprovement(model=gp,
                                   best_f=train_y_tensor.max())
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
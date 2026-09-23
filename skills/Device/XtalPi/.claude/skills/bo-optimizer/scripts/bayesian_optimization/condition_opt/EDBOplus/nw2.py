def _suggest_experiments_impl(self, prev_res=None, batch_size=5, valid_combos=None, valid_x=None):
        # Initialize valid_combos and valid_x if not provided
        if valid_combos is None:
            valid_combos = self.all_combos.copy()
        if valid_x is None:
            valid_x = self.all_x.copy()
        
        # Initial sampling if no previous results
        if prev_res is None or len(prev_res) == 0:
            return self._initial_sampling(batch_size, valid_combos, valid_x)
        
        # Prepare training data
        domain = self.domain
        col_x = [v.name for v in domain.input_variables]
        col_y = [v.name for v in domain.output_variables]
        num_obj = len(col_y)
        
        # Process training data
        train_y, train_x = self._prepare_training_data(prev_res, domain, col_y, col_x)
        
        # Scale data
        scaler_x, scaler_y = MinMaxScaler(), StandardScaler()
        train_x = scaler_x.fit_transform(train_x)
        train_y = scaler_y.fit_transform(train_y)
        
        # Get Pareto front
        pareto_y = pareto_front_2_dim(train_y)
        
        # Set reference point
        ref_mins = np.min(train_y, axis=0)
        ref_point = scaler_y.transform([ref_mins])[0]
        
        # Build models
        models = []
        for i in range(num_obj):
            train_x_i = torch.tensor(train_x).to(**tkwargs).double()
            train_y_i = train_y[:, i]
            train_y_i = np.atleast_2d(train_y_i).reshape(len(train_y_i), -1)
            train_y_i = torch.tensor(train_y_i.tolist()).to(**tkwargs).double()
            sizegbx = train_x_i.element_size() * train_x_i.numel() / 1024**3
            sizegby = train_y_i.element_size() * train_y_i.numel() / 1024**3
            print(f"训练数据大小: X={sizegbx:.2f} GB, Y={sizegby:.2f} GB")

            gp, likelihood = model_likelihood(train_x=train_x_i, train_y=train_y_i)
            model_i = SingleTaskGP(
                train_X=train_x_i,
                train_Y=train_y_i,
                covar_module=gp.covar_module,
                likelihood=likelihood,
            )
            models.append(model_i)
        
        bigmodel = ModelListGP(*models)
        
        # Prepare candidate points
        prev_comb = prev_res[col_x].copy()
        combos = pd.concat([valid_combos, prev_comb]).reset_index()
        combos.index = range(len(combos))
        combos.drop_duplicates(keep=False, inplace=True)
        combos_index = combos.index
        
        # Setup acquisition function
        sampler = SobolQMCNormalSampler(torch.Size([self.sobol_num_samples]), seed=1145141)
        partitioning = NondominatedPartitioning(
            ref_point=torch.tensor(ref_point).float(), 
            Y=torch.tensor(pareto_y).float()
        )
        
        EHVI = qExpectedHypervolumeImprovement(
            model=bigmodel,
            sampler=sampler,
            ref_point=ref_point,
            partitioning=partitioning,
        )
        
        # Optimize acquisition function
        test_x = valid_x.copy()
        test_x = torch.tensor(scaler_x.transform(test_x)).double().to(**tkwargs)
        sizegbtestx = test_x.element_size() * test_x.numel() / 1024**3
        print(f"候选点大小: X={sizegbtestx:.2f} GB")
        acq_result = optimize_acqf_discrete(
            acq_function=EHVI, 
            choices=test_x, 
            q=batch_size, 
            unique=True
        )
        
        # Get best samples
        best_samples = acq_result[0].detach().cpu().numpy()
        ans_indexs = []
        for sample in best_samples:
            d_i = cdist([sample], test_x, metric="cityblock")
            a = np.argmin(d_i)
            ans_indexs.append(a)
        
        return valid_combos.iloc[ans_indexs]
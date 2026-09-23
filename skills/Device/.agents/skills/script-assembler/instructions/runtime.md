# Runtime 编写规范

runtime{}中啥都不用改，直接复制一下内容作为配置
```
    runtime
		(Mode = 'Normal', EnableVerboseLogging = 'No', AutoOffline = 'No', 
		AllowNewIterationsOnDeviceError = 'No', EnableCongestionDetection = 'No', 
		CongestionClearQueueTimeThreshold = '00:02:00', MaxQueueTimeThreshold = '00:05:00', 
		DynamicLids = 'No', EnableBatchModificationByOperator = 'No', 
		IsAccelerated = 'Yes', IsHybridExecution = 'No', AuditOnSimulate = 'No', 
		LogOnSimulate = 'No', EnableSimulationEmailNotification = 'No', 
		HibernateOnSimulate = 'No', EnableFixedStartTime = 'Yes', 
		SimulationStartTime = '9/29/2021 12:00:00 AM', EnableExperiments = 'Yes', 
		EnableCampaigns = 'Yes', EnableInspire = 'Yes', EnableHorizon = 'Yes', 
		ContainerLoadPrompting = 'Yes', ContainerUnloadPrompting = 'Yes', 
		AutoUnload = 'No', AutoLoad = 'No') ;
```


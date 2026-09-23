# Pools 编写规范

pools{}中啥都不用改，直接复制以下内容作为pools的设置

```
    pools
	{
		OperationPool Pool_ATC
			(Strategy = 'Priority First Available', SkipError = 'No', 
			SkipOffline = 'No', OfflineSkipDuration = '00:00:00', 
			SkipUndocked = 'No', UndockedSkipDuration = '00:00:00') ATC_1,ATC_2,ATC_3 ;
		OperationPool Pool_Cytomat2_Tos
			(Strategy = 'Priority First Available', SkipError = 'No', 
			SkipOffline = 'No', OfflineSkipDuration = '00:00:00', 
			SkipUndocked = 'No', UndockedSkipDuration = '00:00:00') CYTOMAT_2_Tos1,CYTOMAT_2_Tos2 ;
	}
```
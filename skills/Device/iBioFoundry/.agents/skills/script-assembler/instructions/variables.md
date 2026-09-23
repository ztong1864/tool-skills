# Variables 编写规范

variables{}中啥都不用改，直接复制以下内容作为配置

```
    variables
	{
		Integer AATIFinished
			(DefaultValue = '0', PromptForValue = 'No', Persist = 'No', 
			Shared = 'Iteration', Capacity = '1');
		Integer Count_iteration
			(DefaultValue = '0', PromptForValue = 'No', Persist = 'No', 
			Shared = 'Iteration', Capacity = '1');
		String lock_CentrifugeLoader
			(PromptForValue = 'No', Persist = 'No', Shared = 'Iteration', 
			Capacity = '1');
		String Lock_Clariostar
			(PromptForValue = 'No', Persist = 'No', Shared = 'Iteration', 
			Capacity = '1');
		String Lock_Echo
			(PromptForValue = 'No', Persist = 'No', Shared = 'Iteration', 
			Capacity = '1');
		String Lock_EVO
			(PromptForValue = 'No', Persist = 'No', Shared = 'Iteration', 
			Capacity = '1');
		String Lock_Fluent
			(PromptForValue = 'No', Persist = 'No', Shared = 'Iteration', 
			Capacity = '1');
		String Lock_Rotanta
			(PromptForValue = 'No', Persist = 'No', Shared = 'Iteration', 
			Capacity = '1');
		Integer subculture
			(DefaultValue = '1', PromptForValue = 'No', Persist = 'No', 
			Shared = 'Iteration', Capacity = '1');
		Integer TecanTips
			(DefaultValue = '0', PromptForValue = 'No', Persist = 'No', 
			Shared = 'Iteration', Capacity = '1');
		Integer test
			(DefaultValue = '0', PromptForValue = 'No', Persist = 'No', 
			Shared = 'Iteration', Capacity = '1');
	}
```
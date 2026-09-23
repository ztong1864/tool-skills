# Devices 编写规范

devices中啥都不用改，直接复制以下代码作为devices的内容：

```
    devices
	{
		ResolvexA200 A200
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Hotel A200_Hotel
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		ALPS3000 ALPS3000
			(PreHeatingTemperature = '140', SealHeight = '0', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		ATC ATC_1
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		ATC ATC_2
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		ATC ATC_3
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		ATC ATC_384
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		ApplicationLauncherUtility ApplicationLauncher
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Arktic Arktic
			(OrdersLocation = 'C:\\ProgramData\\SPTLabtech\\arktic\\Orders', 
			MaxDuration = '00:00:30', Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		AttuneNxT AttuneNxT
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		KeyenceSR710 BC_Reader_DNA
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		KeyenceSR710 BC_Reader_Micro
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Beacon Beacon
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Cytomat10 CYTOMAT_10C
			(CO2Deadband = '2', CO2Enable = 'No', CO2HiHiLimit = '55', 
			CO2HiLimit = '50', CO2LoLimit = '40', CO2LoLoLimit = '35', 
			HumidityDeadband = '2', HumidityEnable = 'No', HumidityHiHiLimit = '75', 
			HumidityHiLimit = '70', HumidityLoLimit = '30', HumidityLoLoLimit = '25', 
			O2Deadband = '2', O2Enable = 'No', O2HiHiLimit = '75', 
			O2HiLimit = '70', O2LoLimit = '60', O2LoLoLimit = '55', 
			TemperatureDeadband = '2', TemperatureEnable = 'No', 
			TemperatureHiHiLimit = '45', TemperatureHiLimit = '39', 
			TemperatureLoLimit = '35', TemperatureLoLoLimit = '30', 
			ShakeDuringIncubate = 'No', ShakeWhenInitialized = 'No', 
			StopShakingWhenOffline = 'No', RPMT1 = '100', RPMT2 = '100', 
			ShakingFrequency = '12', ShakingAmplitude = '50', ScanBarcodeOnGet = 'No', 
			Use20CharBarcode = 'No', SubstituteGetPutWithTransfer = 'No', 
			ManagedTransferStation = 'No', FAMModeEnabled = 'No', 
			SearchMode = 'Entire Device', HotelsOccupancyLabel = '<Click to Edit ...>', 
			ContainersParticipationLabel = '<Click to Edit ...>', 
			IncubateTimeout = '00:00:00', IncubateTimeoutHeatOff = 'No', 
			LowerElevatorAfterAccess = 'No', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		Cytomat2C4 CYTOMAT_2_Tos1
			(CO2Deadband = '2', CO2Enable = 'No', CO2HiHiLimit = '55', 
			CO2HiLimit = '50', CO2LoLimit = '40', CO2LoLoLimit = '35', 
			HumidityDeadband = '2', HumidityEnable = 'No', HumidityHiHiLimit = '75', 
			HumidityHiLimit = '70', HumidityLoLimit = '30', HumidityLoLoLimit = '25', 
			O2Deadband = '2', O2Enable = 'No', O2HiHiLimit = '75', 
			O2HiLimit = '70', O2LoLimit = '60', O2LoLoLimit = '55', 
			TemperatureDeadband = '2', TemperatureEnable = 'No', 
			TemperatureHiHiLimit = '45', TemperatureHiLimit = '39', 
			TemperatureLoLimit = '35', TemperatureLoLoLimit = '30', 
			ShakeDuringIncubate = 'Yes', ShakeWhenInitialized = 'No', 
			StopShakingWhenOffline = 'No', RPMT1 = '1000', RPMT2 = '1000', 
			ShakingFrequency = '12', ShakingAmplitude = '50', ScanBarcodeOnGet = 'No', 
			Use20CharBarcode = 'No', SubstituteGetPutWithTransfer = 'No', 
			ManagedTransferStation = 'No', FAMModeEnabled = 'No', 
			SearchMode = 'Entire Device', HotelsOccupancyLabel = '<Click to Edit ...>', 
			ContainersParticipationLabel = '<Click to Edit ...>', 
			IncubateTimeout = '00:00:00', IncubateTimeoutHeatOff = 'No', 
			LowerElevatorAfterAccess = 'No', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		Cytomat2C4 CYTOMAT_2_Tos2
			(CO2Deadband = '2', CO2Enable = 'No', CO2HiHiLimit = '55', 
			CO2HiLimit = '50', CO2LoLimit = '40', CO2LoLoLimit = '35', 
			HumidityDeadband = '2', HumidityEnable = 'No', HumidityHiHiLimit = '75', 
			HumidityHiLimit = '70', HumidityLoLimit = '30', HumidityLoLoLimit = '25', 
			O2Deadband = '2', O2Enable = 'No', O2HiHiLimit = '75', 
			O2HiLimit = '70', O2LoLimit = '60', O2LoLoLimit = '55', 
			TemperatureDeadband = '2', TemperatureEnable = 'No', 
			TemperatureHiHiLimit = '45', TemperatureHiLimit = '39', 
			TemperatureLoLimit = '35', TemperatureLoLoLimit = '30', 
			ShakeDuringIncubate = 'Yes', ShakeWhenInitialized = 'No', 
			StopShakingWhenOffline = 'No', RPMT1 = '1000', RPMT2 = '1000', 
			ShakingFrequency = '12', ShakingAmplitude = '50', ScanBarcodeOnGet = 'No', 
			Use20CharBarcode = 'No', SubstituteGetPutWithTransfer = 'No', 
			ManagedTransferStation = 'No', FAMModeEnabled = 'No', 
			SearchMode = 'Entire Device', HotelsOccupancyLabel = '<Click to Edit ...>', 
			ContainersParticipationLabel = '<Click to Edit ...>', 
			IncubateTimeout = '00:00:00', IncubateTimeoutHeatOff = 'No', 
			LowerElevatorAfterAccess = 'No', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		Dim4Carousel Carousel
			(FAMModeEnabled = 'No', SearchMode = 'Entire Device', 
			HotelsOccupancyLabel = '<Click to Edit ...>', ContainersParticipationLabel = '<Click to Edit ...>', 
			Speed = '50', Acceleration = '50', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		CentrifugeLoader CentrifugeLoader
			(CentrifugeLoaderProfileName = 'Loader', LoadUnloadSpeed = 'Medium', 
			CounterWeight = 'Unknown', GripperOffsetFixedValue = '8', 
			GripperOffsetPlateAttributeDefault = '8', GripperOffsetMode = 'Half of Plate Height', 
			IgnoreOpticalPlateSensor = 'Yes', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		ChromeleonVanquish ChromeleonVanquish
			(DataVault = 'ChromeleonData', Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Clariostar Clariostar
			(ProtocolPathListUI = '<Click Button to Edit>', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		MultidropCombi Combi
			(ValvePortsUI = '0', InitFluid = 'Default Fluid', PrimeWhenIdle = 'No', 
			PrimeOnInitialization = 'Yes', PrimeVolumeWhenIdle = '10', 
			PrimeIntervalWhenIdle = '5', CassetteID = '1', ChangeCassetteAtRuntime = 'No', 
			Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		ContainerScanner ContainerScanner
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		CytomatHotel Cytomat_10H
			(ShakeDuringIncubate = 'No', ShakeWhenInitialized = 'No', 
			StopShakingWhenOffline = 'No', RPMT1 = '100', RPMT2 = '100', 
			ShakingFrequency = '12', ShakingAmplitude = '50', ScanBarcodeOnGet = 'No', 
			Use20CharBarcode = 'No', SubstituteGetPutWithTransfer = 'No', 
			ManagedTransferStation = 'No', FAMModeEnabled = 'No', 
			SearchMode = 'Entire Device', HotelsOccupancyLabel = '<Click to Edit ...>', 
			ContainersParticipationLabel = '<Click to Edit ...>', 
			IncubateTimeout = '00:00:00', IncubateTimeoutHeatOff = 'No', 
			LowerElevatorAfterAccess = 'No', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		CytomatHotel Cytomat_24H
			(ShakeDuringIncubate = 'No', ShakeWhenInitialized = 'No', 
			StopShakingWhenOffline = 'No', RPMT1 = '100', RPMT2 = '100', 
			ShakingFrequency = '12', ShakingAmplitude = '50', ScanBarcodeOnGet = 'No', 
			Use20CharBarcode = 'No', SubstituteGetPutWithTransfer = 'No', 
			ManagedTransferStation = 'No', FAMModeEnabled = 'No', 
			SearchMode = 'Entire Device', HotelsOccupancyLabel = '<Click to Edit ...>', 
			ContainersParticipationLabel = '<Click to Edit ...>', 
			IncubateTimeout = '00:00:00', IncubateTimeoutHeatOff = 'No', 
			LowerElevatorAfterAccess = 'No', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		Cytomat2C4 Cytomat_2C425
			(CO2Deadband = '2', CO2Enable = 'No', CO2HiHiLimit = '55', 
			CO2HiLimit = '50', CO2LoLimit = '40', CO2LoLoLimit = '35', 
			HumidityDeadband = '2', HumidityEnable = 'No', HumidityHiHiLimit = '75', 
			HumidityHiLimit = '70', HumidityLoLimit = '30', HumidityLoLoLimit = '25', 
			O2Deadband = '2', O2Enable = 'No', O2HiHiLimit = '75', 
			O2HiLimit = '70', O2LoLimit = '60', O2LoLoLimit = '55', 
			TemperatureDeadband = '2', TemperatureEnable = 'No', 
			TemperatureHiHiLimit = '45', TemperatureHiLimit = '39', 
			TemperatureLoLimit = '35', TemperatureLoLoLimit = '30', 
			ShakeDuringIncubate = 'No', ShakeWhenInitialized = 'No', 
			StopShakingWhenOffline = 'No', RPMT1 = '100', RPMT2 = '100', 
			ShakingFrequency = '12', ShakingAmplitude = '50', ScanBarcodeOnGet = 'No', 
			Use20CharBarcode = 'No', SubstituteGetPutWithTransfer = 'No', 
			ManagedTransferStation = 'No', FAMModeEnabled = 'No', 
			SearchMode = 'Entire Device', HotelsOccupancyLabel = '<Click to Edit ...>', 
			ContainersParticipationLabel = '<Click to Edit ...>', 
			IncubateTimeout = '00:00:00', IncubateTimeoutHeatOff = 'No', 
			LowerElevatorAfterAccess = 'No', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		Cytomat2C4 Cytomat_2C450
			(CO2Deadband = '2', CO2Enable = 'No', CO2HiHiLimit = '55', 
			CO2HiLimit = '50', CO2LoLimit = '40', CO2LoLoLimit = '35', 
			HumidityDeadband = '2', HumidityEnable = 'No', HumidityHiHiLimit = '75', 
			HumidityHiLimit = '70', HumidityLoLimit = '30', HumidityLoLoLimit = '25', 
			O2Deadband = '2', O2Enable = 'No', O2HiHiLimit = '75', 
			O2HiLimit = '70', O2LoLimit = '60', O2LoLoLimit = '55', 
			TemperatureDeadband = '2', TemperatureEnable = 'No', 
			TemperatureHiHiLimit = '45', TemperatureHiLimit = '39', 
			TemperatureLoLimit = '35', TemperatureLoLoLimit = '30', 
			ShakeDuringIncubate = 'No', ShakeWhenInitialized = 'No', 
			StopShakingWhenOffline = 'No', RPMT1 = '100', RPMT2 = '100', 
			ShakingFrequency = '12', ShakingAmplitude = '50', ScanBarcodeOnGet = 'No', 
			Use20CharBarcode = 'No', SubstituteGetPutWithTransfer = 'No', 
			ManagedTransferStation = 'No', FAMModeEnabled = 'No', 
			SearchMode = 'Entire Device', HotelsOccupancyLabel = '<Click to Edit ...>', 
			ContainersParticipationLabel = '<Click to Edit ...>', 
			IncubateTimeout = '00:00:00', IncubateTimeoutHeatOff = 'No', 
			LowerElevatorAfterAccess = 'No', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		DataBuilder DataBuilder
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		DataMiner DataMiner
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Docking Docking
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Echo5XX Echo
			(OutputPathListUI = '<Click Button to Edit>', LeaveBubblerPumpRunning = 'True', 
			SkipPlatePropertyValidation = 'False', InsertsDictionary = 'Nest 1~SOURCE PLATE W/2.10 MM INSET;Nest 2~SOURCE PLATE W/4.50 MM INSET', 
			InsertsOffsets = 'SOURCE PLATE W/2.10 MM INSET~1,0,-9.75;SOURCE PLATE W/4.50 MM INSET~1,1,-10.5', 
			SetBarcodeCheck = 'No', Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Hotel Echo_Hotel
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		GenericMover F7_1
			(ParkLocation = 'STDloc:safe', ParkMoverAtEndOfRun = 'Yes', 
			MotionSettings = 'Velocity: 50%, Acceleration: 25%, Jerk: 100%', 
			AllowLidding = 'Yes', AttendedActionForNoCode = 'Prompt', 
			UnattendedActionForNoCode = 'Warning', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		RotationStation F7_1_Rotation
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		GenericMover F7_2
			(ParkLocation = 'STDloc:safe', ParkMoverAtEndOfRun = 'Yes', 
			MotionSettings = 'Velocity: 50%, Acceleration: 25%, Jerk: 100%', 
			AllowLidding = 'Yes', AttendedActionForNoCode = 'Prompt', 
			UnattendedActionForNoCode = 'Warning', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		FileManager FileManager
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Fluent Fluent
			(ParkScript = 'park', HandleLabwareInTransfer = 'No', 
			Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		FreedomEVO FreedomEVO
			(ProtocolPath = '\\\\10.0.0.12\\c\\ProgramData\\Tecan\\EVOware\\database\\scripts', 
			ParkScript = 'Park.esc', ExecuteParkMethod = 'Yes', 
			UserName = 'Admin', UserPass = 'tecan2024', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		Wtio GPIO_Moxa1
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Wtio GPIO_Moxa2
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Wtio GPIO_Regrips
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Infinity Infinity
			(CapillarySize = '33 cm', ProtocolPathListUI = '<Click Button to Edit>', 
			Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		IntelliXcap96 IntelliXcap96
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		KBSWasp KBSWasp_sealer
			(PreHeatingTemperature = '155', SealHeight = '0', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		AgilentMicroplateLabeler Labeler
			(ProfileName = 'ethernet', Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Wtio LidPark_IO
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Lidpark Lidpark
			(RegripBeforeLidDelid = 'Yes', DelidToStorageNests = 'No', 
			LidFromStorageNests = 'No', Active = 'Inactive', TakeOfflineDuringChangeout = 'Yes');
		MomentumOperator MomentumOperator
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		QuantStudio7Pro QuantStudio7Pro
			(ProtocolPathListUI = '<Click to Edit Paths>', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		Regrip Regrip_1
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Regrip Regrip_2
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Centrifuge Rotanta460
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Loader SideLoader
			(MotionSettings = 'Velocity: 100%, Acceleration: 100%, Jerk: 100%', 
			Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		GenericMover SpinnakerBT
			(ParkLocation = 'STDloc:safe', ParkMoverAtEndOfRun = 'Yes', 
			MotionSettings = 'Velocity: 70%, Acceleration: 70%, Jerk: 70%', 
			AllowLidding = 'Yes', AttendedActionForNoCode = 'Prompt', 
			UnattendedActionForNoCode = 'Warning', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		Hotel Staging_Nests
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		SwapStation SwapStation_F7_1_2
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		SwapStation SwapStation_F7_2_3
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		Unite Unite_WellNOTrans
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		VisionMateSuite VisionMate
			(FlagDuplicateScanResults = 'No', Active = 'Active', 
			TakeOfflineDuringChangeout = 'Yes');
		Waste Waste
			(Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
		XPeel XPeel
			(ElevateWarningsToErrors = 'No', IgnoreSealNotRemovedErrors = 'Yes', 
			EnablePlatePresenceCheck = 'No', GetRemainingSealsOnStartup = 'No', 
			Active = 'Active', TakeOfflineDuringChangeout = 'Yes');
	}
```


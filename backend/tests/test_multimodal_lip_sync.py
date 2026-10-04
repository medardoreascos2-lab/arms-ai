from backend.multimodal.lip_sync import LipSyncSequence,MouthCue,SyntheticLipSyncProvider
def test_synthetic_lip_sync_returns_deterministic_timing_only():
 sequence=LipSyncSequence("synthetic-audio:1",200,(MouthCue(0,100,"A"),MouthCue(100,200,"REST")),"LOCAL_TEST_ONLY_SYNTHETIC_LIP_SYNC",True);provider=SyntheticLipSyncProvider({"synthetic-audio:1":sequence});assert provider.audio_timing("synthetic-audio:1")==200 and provider.viseme_timing("synthetic-audio:1")==sequence.cues

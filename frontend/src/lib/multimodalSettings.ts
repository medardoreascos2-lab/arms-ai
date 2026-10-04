export const multimodalSettings = [
 {id:"VOICE",title:"Voice",detail:"Off until explicitly enabled for a session.",status:"OFF"},
 {id:"CAMERA",title:"Camera",detail:"Off. Start requires explicit action and visible consent.",status:"OFF"},
 {id:"AVATAR",title:"Avatar",detail:"Presentation placeholder only.",status:"OFF"},
 {id:"NOTIFICATIONS",title:"Notifications",detail:"In-app available; external delivery unavailable.",status:"IN_APP_ONLY"},
 {id:"PRESENCE",title:"Presence",detail:"Unknown until explicitly enabled.",status:"UNKNOWN"},
 {id:"QUIET_HOURS",title:"Quiet hours",detail:"Noncritical voice and avatar interruptions are suppressed.",status:"READY"},
 {id:"PRIVACY",title:"Privacy",detail:"Sensitive modality consent is session-scoped and revocable.",status:"READY"},
 {id:"RETENTION",title:"Retention",detail:"Audio, image, and camera data default to no storage.",status:"NO_STORAGE"},
] as const;

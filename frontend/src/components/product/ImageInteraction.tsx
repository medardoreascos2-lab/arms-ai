"use client";
import { useEffect,useState } from "react";
import styles from "./ImageInteraction.module.css";

type ImageState="EMPTY"|"READY"|"INTEGRATION_PENDING";
export function ImageInteraction(){
 const [preview,setPreview]=useState<string|null>(null);const [name,setName]=useState<string|null>(null);const [consent,setConsent]=useState(false);const [state,setState]=useState<ImageState>("EMPTY");
 useEffect(()=>()=>{if(preview)URL.revokeObjectURL(preview)},[preview]);
 function select(file: File|null){if(preview)URL.revokeObjectURL(preview);if(!file){setPreview(null);setName(null);setState("EMPTY");return}setPreview(URL.createObjectURL(file));setName(file.name);setState("READY")}
 function remove(){if(preview)URL.revokeObjectURL(preview);setPreview(null);setName(null);setConsent(false);setState("EMPTY")}
 function analyze(){if(preview&&consent)setState("INTEGRATION_PENDING")}
 return <section className={styles.panel} aria-labelledby="image-title">
  <h2 id="image-title">Image interaction</h2><p>Choose a JPEG, PNG, or WEBP image. The preview remains in this browser and is not uploaded by this foundation.</p>
  <label className={styles.picker}>Choose image<input type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>select(e.target.files?.[0]??null)}/></label>
  {preview&&<figure><img src={preview} alt="User-selected local preview"/><figcaption>{name}</figcaption></figure>}
  <label><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> I consent to processing this selected image for this session.</label>
  <div className={styles.controls}><button type="button" onClick={analyze} disabled={!preview||!consent}>Analyze</button><button type="button" onClick={remove} disabled={!preview}>Remove</button></div>
  <dl><div><dt>Processing</dt><dd role="status">{state.replaceAll("_"," ")}</dd></div><div><dt>Result</dt><dd>{state==="INTEGRATION_PENDING"?"No vision provider is configured.":"No result."}</dd></div><div><dt>Provenance</dt><dd>{state==="INTEGRATION_PENDING"?"INTEGRATION_PENDING":"No provider invocation."}</dd></div></dl>
 </section>
}

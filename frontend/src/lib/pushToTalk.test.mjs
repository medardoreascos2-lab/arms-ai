import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source=fs.readFileSync(new URL("../components/product/PushToTalk.tsx",import.meta.url),"utf8");

test("push to talk is explicit and stops every microphone track",()=>{
  assert.match(source,/onClick=\{start\}/); assert.match(source,/getUserMedia\(\{ audio: true, video: false \}\)/);
  assert.match(source,/getTracks\(\)\.forEach\(\(track\) => track\.stop\(\)\)/);
  assert.match(source,/onClick=\{stop\}/); assert.match(source,/onClick=\{cancel\}/);
});

test("voice UI exposes transcript response playback and privacy limitations",()=>{
  for (const text of ["Transcription","MEDAR response","Playback","No background microphone","No voice request is sent"]) assert.match(source,new RegExp(text));
  assert.doesNotMatch(source,/setInterval|localStorage|fetch\(/);
});

import assert from "node:assert/strict";import fs from "node:fs";import test from "node:test";const source=fs.readFileSync(new URL("../components/product/AvatarSurface.tsx",import.meta.url),"utf8");
test("avatar placeholder exposes state transcript voice and privacy",()=>{for(const value of ["OFFLINE","Transcript","Voice","Privacy","Microphone off","Camera off","Presentation only"])assert.match(source,new RegExp(value));});
test("avatar placeholder contains no 3d engine or capture",()=>assert.doesNotMatch(source,/three|webgl|getUserMedia|canvas/i));

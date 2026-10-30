'use strict';
importScripts('/static/cutout-core.js?v=2', '/static/vendor/cutout/ort.wasm.min.js');
ort.env.wasm.wasmPaths = '/static/vendor/cutout/';
ort.env.wasm.numThreads = 1;
ort.env.wasm.proxy = false;
let session;
self.onmessage = async ({data}) => {
  let input, outputs;
  try {
    if(data.mode==='alpha'){
      const mask=CutoutCore.cleanMask(data.input,data.width,data.height);
      self.postMessage({id:data.id,mask},[mask.buffer]);return;
    }
    if (!session) {
      self.postMessage({id:data.id, stage:'loading'});
      session = await ort.InferenceSession.create('/static/vendor/cutout/u2netp.onnx', {executionProviders:['wasm'],graphOptimizationLevel:'all'});
    }
    self.postMessage({id:data.id,stage:'processing'});
    input = new ort.Tensor('float32', data.input, [1,3,320,320]);
    outputs = await session.run({[session.inputNames[0]]:input});
    const mask = CutoutCore.cleanMask(CutoutCore.maskPixels(outputs[session.outputNames[0]].data),320,320);
    self.postMessage({id:data.id,mask},[mask.buffer]);
  } catch {
    self.postMessage({id:data.id,error:'cutout_failed'});
  } finally {
    input?.dispose(); if (outputs) for (const tensor of Object.values(outputs)) tensor.dispose();
  }
};

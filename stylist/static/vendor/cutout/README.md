# Browser foreground segmentation assets

Self-hosted, lazy-loaded in a dedicated Web Worker. No runtime CDN or third-party image-processing request. The worker uses one WASM thread and does not require cross-origin isolation.

- ONNX Runtime Web **1.20.1**, Microsoft, MIT; see `ONNXRUNTIME-LICENSE.txt`. Runtime files fetched from the fixed npm distribution through unpkg, hashes in `manifest.json`. Deployment reference: https://onnxruntime.ai/docs/tutorials/web/deploy.html
- **U2NetP** general foreground model, original project https://github.com/xuebinqin/U-2-Net (Apache-2.0 source license retained in `U2NET-LICENSE.txt`). ONNX conversion distributed by rembg at https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx; fixed 4,574,861-byte asset. MD5 `8e83ca70e441ab06c318d82300c84806` matches rembg's published loader; SHA-256 in manifest. Conversion source/reference: https://github.com/danielgatis/rembg/blob/main/rembg/sessions/u2netp.py

Input: RGB, 320×320, CHW float32; maximum-channel normalization followed by ImageNet means/stds. Output: first saliency mask, min/max normalized. The application validates coverage, scales alpha back to the bounded input image, and trims transparent padding. Original product images and generated user cutouts are not stored in this directory.

All JS, MJS, WASM and ONNX files are required together. Do not change the runtime version without updating the matching WASM/MJS and re-running a real browser inference. Segmentation separates salient foreground, not individual layers of garments on a person; keep original-image fallback for uncertain masks.

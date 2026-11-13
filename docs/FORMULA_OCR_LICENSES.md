# Formula OCR licenses / 公式 OCR 许可证

Verified 2026-11-12 against the pinned model card, installed distribution metadata/licenses,
and upstream primary sources. 依据固定版本模型说明、已安装包的元数据和许可证及上游原始来源核对。

| Component / 组件 | Verified license and redistribution conditions / 许可证与再分发条件 |
|---|---|
| myLibrary adapter and UI | Original project code under this repository's [LICENSE](../LICENSE), PolyForm Noncommercial. This does not change third-party component licenses. 本项目原有许可证不变，不改变第三方许可。 |
| Pix2Text upstream code | [MIT](https://github.com/breezedeus/Pix2Text/blob/main/LICENSE), copyright BreezeDeus. Commercial use and redistribution permitted with the copyright, permission notice and disclaimer retained. The Pix2Text Python package is not installed or bundled by this implementation. MIT，保留版权、许可和免责声明；本实现不安装或打包该 Python 包。 |
| Pix2Text MFR 1.5 weights/tokenizer | The [publisher's model card](https://huggingface.co/breezedeus/pix2text-mfr-1.5) declares MIT; the downloaded card at revision `1cef9f0bdcd6a4c63df7de1311fb0894593340cc` has `license: mit` and is itself checksum-pinned. **Provenance as the card states it:** the model uses Microsoft's TrOCR architecture, "starting with its initial values and retrained using a dataset of mathematical formula images"; that training dataset is not otherwise described, and the card's test data "are derived from real data uploaded by users on the Pix2Text Online Service". The MIT declaration is the publisher's licence for its release: it does **not** by itself establish rights in the training data, which have not been audited (an open release question, THIRD_PARTY_NOTICES.md section 6). MIT permits redistribution subject to notice retention; keep the model card, upstream attribution and MIT terms with any redistributed weights. myLibrary does not bundle or redistribute the weights: each user downloads them from the publisher after an explicit choice, pinned and SHA-256-checked; recognition is then free, local and offline, with no account, API key or fee. 发布者声明 MIT；不等于对训练数据的权利，训练数据未经审计；权重不随发行包附带，由用户明确选择后从发布者处下载。 |
| ONNX Runtime 1.31.1 | [MIT](https://github.com/microsoft/onnxruntime/blob/main/LICENSE). Installed files `onnxruntime/LICENSE` and `onnxruntime/ThirdPartyNotices.txt` must accompany redistributed binaries; the latter covers embedded components. 再分发二进制时保留这两个文件及内含组件的通知。 |
| NumPy 2.5.4 | Main project BSD-3-Clause; installed wheel declares `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`. Its full `numpy-2.5.4.dist-info/licenses/` includes bundled binary dependencies such as OpenBLAS and their conditions. Preserve all these licenses, copyright/disclaimers and binary redistribution notices; do not use names to imply endorsement. [Upstream](https://github.com/numpy/numpy/blob/main/LICENSE.txt). 保留 wheel 中完整许可证目录、版权和声明，不暗示背书。 |
| Pillow 13.0.0 | [MIT-CMU](https://github.com/python-pillow/Pillow/blob/main/LICENSE). Retain copyright and permission notices in copies/supporting documentation; do not use author/Secret Labs names for publicity without permission. The wheel's complete `pillow-13.0.0.dist-info/licenses/LICENSE` also contains its bundled codec notices (including Brotli and other image codecs). Keep the complete file. 保留完整文件，含图像编解码器通知；不擅自用作者名称宣传。 |
| FlatBuffers 25.12.19 | Installed metadata: Apache-2.0. The wheel contains no licence file, so the package supplies it: `package/licenses/FlatBuffers-LICENSE.txt` (verbatim from the project's [v25.12.19 release](https://github.com/google/flatbuffers/blob/v25.12.19/LICENSE)), copied by `build_package.py` into `third_party_licenses/` (2026-11-13); the build stops if any bundled distribution has no licence text. 已补齐：发行包中附带 FlatBuffers 许可证。 |
| packaging 26.3 | `Apache-2.0 OR BSD-2-Clause`, as the installed metadata and its three license files specify. Redistributors may choose an offered license and comply with its notice conditions; retain `packaging-26.3.dist-info/licenses/`. [Upstream](https://github.com/pypa/packaging/blob/main/LICENSE). 双重许可，选择并遵守对应条款；保留许可证目录。 |
| protobuf 7.36.2 | Installed metadata: BSD-3-Clause. Preserve `protobuf-7.36.2.dist-info/LICENSE` and its bundled-component notices; retain copyright, conditions and disclaimer, no implied endorsement. [Upstream](https://github.com/protocolbuffers/protobuf/blob/main/LICENSE). 保留版权、条款、免责声明和内含组件通知，不暗示背书。 |
| KaTeX (already used by notes) | Existing local pinned KaTeX and fonts; its existing bundled license/font notices remain required. No renderer or font was downloaded or changed for this task. 沿用现有本地组件和许可证，本任务未下载或更换。 |

Formula recognition adds no new Python dependency: ONNX Runtime and its transitive NumPy,
FlatBuffers, packaging and protobuf are already present for scan OCR; Pillow is also already
used by that stack. Inference imports ONNX Runtime/NumPy lazily. The optional part is the
model download and using recognition; the existing scan-OCR runtime remains a core dependency
of myLibrary. PyTorch, Transformers, Optimum and remote inference SDKs are not used.
公式功能不增加新的 Python 依赖；模型下载和使用识别是可选的，扫描 OCR 已有运行库仍为核心依赖。

These permissive third-party terms allow use with this application while their own licenses
stay in force. They do not relicense myLibrary for commercial redistribution. The full
inventory of what the ready-to-use package contains, including its LGPL component (GEOS in
Shapely; OpenCV's FFmpeg plugin and ReportLab's unlicensed fonts are left out of the package),
and the open release questions (GEOS source access and legal review, the model's training
data), is in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md); packaging evidence in
[M5_VERIFICATION.md](M5_VERIFICATION.md).
第三方宽松许可不改变 myLibrary 自身许可。发行包的完整清单、LGPL 组件和未决的发行问题见 THIRD_PARTY_NOTICES.md。

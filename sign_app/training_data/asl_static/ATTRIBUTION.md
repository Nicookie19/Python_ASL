# Training data attribution

The bundled landmark training samples are adapted from **ASL Static Landmarks v1** by Neel Ulysses Roda (Hugging Face account: Siruyy).

- Dataset: https://huggingface.co/datasets/Siruyy/asl-static-landmarks-v1
- Source project and preprocessing code: https://github.com/Siruyy/realtime-asl-recognizer/tree/74b976b536ab8318dab756a3071a681d5c75bcb0
- License: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
- Pinned data revision: `a9cea6cf363eb3265ea0e795a1af573105d85f53`

**Changes made:** recovered the 21 XYZ landmark coordinates by reversing the source feature standardization; changed numeric labels into this app's `asl_*` IDs; omitted the motion letters J and Z; removed exact rounded pose duplicates across the source train/test split; mirrored poses during model training; and packaged the resulting landmark arrays as `samples.npz`. The samples do not include source images, signer IDs, or session IDs.

The bundled classifier is trained from the transformed training split. `../../content_packs/asl/model/evaluation.json` records the evaluation metrics, source revision, data checksum, and known limitations. The source's random frame split is not an independent signer test.

### Task 1: Install Dependencies + Download Models

**Files:**
- Modify: `requirements.txt`
- Create: `models/` directory

**Interfaces:**
- Consumes: nothing
- Produces: onnxruntime, scikit-image available; model files in `models/`

- [ ] **Step 1: Add dependencies to requirements.txt**

Append to `requirements.txt`:
```
onnxruntime>=1.17.0
scikit-image>=0.22.0
```

- [ ] **Step 2: Install dependencies**

Run: `.\venv\Scripts\activate; pip install onnxruntime scikit-image -i https://pypi.tuna.tsinghua.edu.cn/simple`

- [ ] **Step 3: Create models directory and download OSNet**

```powershell
mkdir models
# Download OSNet AIN x1.0 (person Re-ID, ONNX format)
# Source: https://github.com/micr.cloudml/OSNet
# For Stage 1, we use a pre-exported ONNX model
# If download fails, create a stub for testing
```

- [ ] **Step 4: Create vehicle Re-ID stub model**

For Stage 1, create a minimal ONNX model stub that outputs 512-dim embeddings. This will be replaced with a real model later.

- [ ] **Step 5: Run existing tests to verify nothing broke**

Run: `.\venv\Scripts\activate; pytest tests/ -v`
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add requirements.txt models/
git commit -m "Phase 2: add onnxruntime, scikit-image dependencies and model directory"
```

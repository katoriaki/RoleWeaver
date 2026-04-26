# Qwen3.5 9B LoRA Training Reference

This folder keeps a cleaned-up copy of the original offline LoRA training workflow used before RoleWeaver was generalized.

These scripts are examples for users who want to train their own adapter. RoleWeaver itself only needs:

- a base model path
- a trained LoRA adapter path
- an optional `SKILL.md` path

## Files

- `train_qwen35_lora_offline.py`: offline LoRA SFT training script for Qwen3.5-9B style local checkpoints.
- `convert_excel_to_jsonl.py`: convert a two-column Excel/CSV table into the JSONL format used by the trainer.
- `role_sft_template.xlsx`: standard user/assistant Excel template for users who prefer spreadsheets.
- `probe_base_model.py`: quick base-model smoke test.
- `inspect_jsonl_dataset.py`: load and inspect a JSONL SFT dataset.
- `probe_lora_adapter.py`: load a trained LoRA adapter and test several prompts.

## Expected Dataset Format

The web UI and API accept either:

- Excel/CSV table: first row is `user, assistant`; data starts from row 2.
- JSONL rows with a `messages` field:

```json
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

Manual Excel/CSV conversion:

```bash
python convert_excel_to_jsonl.py \
  --input role_sft_template.xlsx \
  --output role_sft.jsonl
```

## Example

```bash
python train_qwen35_lora_offline.py \
  --model-path /public/huggingface-models/Qwen/Qwen3.5-9B \
  --data-file meiling_sft_updated_v2.jsonl \
  --output-dir ./your-role-qwen35-9b-lora
```

Then fill `roleweaver.config.csv`:

```csv
key,value,notes
base_model_path,/public/huggingface-models/Qwen/Qwen3.5-9B,Required
lora_path,./your-role-qwen35-9b-lora,Required
skill_file,./your-role/SKILL.md,Optional
```

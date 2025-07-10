set -e
cd ../LLaMA-Factory
MODEL_PATH=""
model_name=""
image_resolution=180000
template="qwen2_vl"
cutoff_len=32768
dataset=""
per_device_train_batch_size=1
gradient_accumulation_steps=1
lr=1.0e-5
epoch=1.0

temp_lr=$(echo $lr | tr '.' 'd')
temp_epoch=$(echo $epoch | tr '.' 'd')
wandb_run_name=${model_name}_ir${image_resolution}_ds_${dataset}_ct${cutoff_len}_lr${temp_lr}_pbs${per_device_train_batch_size}_g${gradient_accumulation_steps}_e${temp_epoch}

OUTPUT_PATH=./results/${wandb_run_name}
mkdir -p $OUTPUT_PATH

echo $OUTPUT_PATH

sed -e "s|{model_path}|$MODEL_PATH|" \
    -e "s|{image_resolution}|$image_resolution|" \
    -e "s|{dataset}|$dataset|" \
    -e "s|{template}|$template|" \
    -e "s|{cutoff_len}|$cutoff_len|" \
    -e "s|{output_path}|$OUTPUT_PATH|" \
    -e "s|{per_device_train_batch_size}|$per_device_train_batch_size|" \
    -e "s|{gradient_accumulation_steps}|$gradient_accumulation_steps|" \
    -e "s|{lr}|$lr|" \
    -e "s|{epoch}|$epoch|" \
    -e "s|{wandb_run_name}|$wandb_run_name|" \
    ../finetune/full/template.yaml > ./examples/train_full/$wandb_run_name.yaml

# export CUDA_VISIBLE_DEVICES=
# export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
# export WANDB_DISABLED=False
# export WANDB_API_KEY=your_wandb_api_key
# export PYTHONUNBUFFERED=1
# export FORCE_TORCHRUN=1

llamafactory-cli train ./examples/train_full/$wandb_run_name.yaml


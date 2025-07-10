set -e
cd ../LLaMA-Factory
# 1. 修改模型路径
MODEL_PATH=""
model_name=""
merge_output_path="" # 合并模型的输出路径

# 2. image_resolution默认为262144，即512x512, 
image_resolution=262144

# 3. template默认为qwen2_vl, 可选 qwen2_5_vl
template="qwen2_vl"

# 4. cutoff_len设置最大上下文长度
cutoff_len=16384

# 5. 设置dataset
dataset=""

# 6. 设置lora参数
lora_rank=8
quantization_bit=4 # choices: [bitsandbytes (4/8), hqq (2/3/4/5/6/8), eetq (8)]
quantization_method=bitsandbytes # 

# 7. 设置bs和lr、epoch
per_device_train_batch_size=1
gradient_accumulation_steps=1
lr=1.0e-5
epoch=3.0

temp_lr=$(echo $lr | tr '.' 'd')
temp_epoch=$(echo $epoch | tr '.' 'd')
wandb_run_name=${model_name}_lora_ir${image_resolution}_ds${dataset}_ct${cutoff_len}_lr${temp_lr}_pbs${per_device_train_batch_size}_g${gradient_accumulation_steps}_e${temp_epoch}

# 8. 修改保存路径
OUTPUT_PATH=./results/${wandb_run_name}
mkdir -p $OUTPUT_PATH
echo $OUTPUT_PATH

# 9. 修改yaml文件
sed -e "s|{model_path}|$MODEL_PATH|" \
    -e "s|{image_resolution}|$image_resolution|" \
    -e "s|{lora_rank}|$lora_rank|" \
    -e "s|{quantization_bit}|$quantization_bit|" \
    -e "s|{quantization_method}|$quantization_method|" \
    -e "s|{dataset}|$dataset|" \
    -e "s|{template}|$template|" \
    -e "s|{cutoff_len}|$cutoff_len|" \
    -e "s|{output_path}|$OUTPUT_PATH|" \
    -e "s|{per_device_train_batch_size}|$per_device_train_batch_size|" \
    -e "s|{gradient_accumulation_steps}|$gradient_accumulation_steps|" \
    -e "s|{lr}|$lr|" \
    -e "s|{epoch}|$epoch|" \
    -e "s|{wandb_run_name}|$wandb_run_name|" \
    ../finetune/lora/template.yaml > ./examples/train_lora/$wandb_run_name.yaml

# 10. 启动wandb需要导入wandb的API_KEY
# export NCCL_P2P_DISABLE=1 # 关闭NCCL P2P
# export WANDB_DISABLED=True
# export WANDB_API_KEY=your_api_key
# export PYTHONUNBUFFERED=1 # 输出不缓冲
# export FORCE_TORCHRUN=1 
# export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

llamafactory-cli train ./examples/train_lora/$wandb_run_name.yaml

# export CUDA_VISIBLE_DEVICES="0" # 一张卡就可以merge

sed -e "s|{model_path}|$MODEL_PATH|" \
    -e "s|{adapter_path}|$OUTPUT_PATH|" \
    -e "s|{output_path}|$merge_output_path|" \
    ../finetune/lora/template.yaml > ./examples/merge_lora/qwen2_vl_lora_merge.yaml

llamafactory-cli export ./examples/merge_lora/qwen2_vl_lora_merge.yaml
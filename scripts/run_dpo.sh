cd dpo_tuning;
export NCCL_IB_GID_INDEX=3
export NCCL_P2P_DISABLE=1
export NCCL_P2P_LEVEL=NVL
accelerate launch --num_processes $1 --gpu_ids $2 run.py --path_to_source ../datasets/new_DINO_gold_dataset_with_prompt_boxes.csv;


cd ~/cunning_manipulator/dpo_experiment;
export NCCL_IB_GID_INDEX=3
export NCCL_P2P_DISABLE=1
export NCCL_P2P_LEVEL=NVL
accelerate launch --num_processes 2 --gpu_ids 0,1 run.py;

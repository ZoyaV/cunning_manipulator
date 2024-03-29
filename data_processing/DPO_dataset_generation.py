import sys
sys.path.append("../")
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..')) 

os.system('pwd')
import numpy as np
import torch
from torchvision.ops import box_convert
from groundingdino.util.inference import load_model, load_image, predict
import pandas as pd
from transformers import HfArgumentParser
from dpo_tuning.training_arguments import ProcessingArguments
import statistics
import re
import random
from dpo_tuning.utils.metrics import box_iou
from one_peace.models import from_pretrained
from dpo_tuning.utils.data import prepare_data
from dpo_tuning.utils.detector import get_Dino_predictions, get_ONE_PEACE_predictions, get_images
import tqdm


def init_detector_model():
    Dino = load_model("./GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py",\
                       "./GroundingDINO/weights/groundingdino_swint_ogc.pth")
    return Dino

def init_onepeace():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = from_pretrained(
      "ONE-PEACE_Grounding",
        model_type="one_peace_classify",
        device=device,
        dtype="float32"
        )
    return model

def get_objects_descriptions(ds: pd.DataFrame):
    object_descriptions = {}
    for i in range(len(ds)):
        if ds['item_id'][i] in object_descriptions.keys():
            object_descriptions[ds['item_id'][i]].append([i,ds['description'][i]])
        else:
            object_descriptions[ds['item_id'][i]] = [[i, ds['description'][i]]]
    return object_descriptions

def evaluate_descriptions(model_name, path_to_imgs, path_to_output, path_to_source, use_score, ranking_strategy,threshhold=None):
    correct_reward_iou = []  
    correct_reward_score = []
    means = []
    prompt_bboxes = []
    if model_name == "DINO":
        model = init_detector_model()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(device)
        model.to(device)
    elif model_name == 'onepeace':
        model = init_onepeace()
    ds = pd.read_csv(path_to_source, sep=',', header=0)
    for i in tqdm.tqdm(range(len(ds))):
        correct = ds['description'][i]
        name, img_sources, images = get_images(ds['item_id'][i], path_to_imgs)
        if use_score == True and ds["score"][i] == -1:
            correct_reward_iou.append(-1.0)
            correct_reward_score.append(0.0)
            means.append(0.0)
            prompt_bboxes.append([0,0,0,0])
            continue
        elif model_name.lower() == 'dino':
            predicted_bbox, pred_score = get_Dino_predictions(model, images, img_sources, correct)
        elif model_name.lower() == 'onepeace':
            predicted_bbox = get_ONE_PEACE_predictions(model, str(path_to_imgs)+str(name), str(correct))[0]
            pred_score = 1
        try: 
            dataset_bbox = torch.Tensor([[float(x) for x in re.split(',', ds['true_bbox'][i][1:-1])]])
            real_bbox = box_convert(boxes=dataset_bbox, in_fmt="xywh", out_fmt="xyxy").numpy()[0] 
            iou_score = float(box_iou(real_bbox, predicted_bbox))
        except Exception as e:
            iou_score = 0.0
            pred_score = 0.0
            print(f"Exception: {e}")
        correct_reward_iou.append(iou_score)
        correct_reward_score.append(pred_score)
        prompt_bboxes.append(predicted_bbox)
        means.append(statistics.harmonic_mean([iou_score, pred_score]))
        print(i, '\\', iou_score)
    ds['response_iou'] = correct_reward_iou
    ds['response_score'] = correct_reward_score
    ds['harmonic_mean'] = means
    ds['description_bbox'] = prompt_bboxes
    if ranking_strategy.lower() == 'iou':
        ds['rank'] = correct_reward_iou
    elif ranking_strategy.lower() == 'score':
        ds['rank'] = correct_reward_score
    elif ranking_strategy.lower() == 'mean':
        ds['rank'] = means
    elif ranking_strategy.lower() == 'threshhold':
        values = []
        if not threshhold:
            threshhold=0.7
        for i in range(len(correct_reward_iou)):
            if correct_reward_iou[i]>threshhold:
                values.append(correct_reward_score[i])
            else:
                values.append(0.0)
        ds['rank'] = means
    ds.to_csv(path_to_output, index=False)
    return ds


def generate_triplets(path_to_output, ds=None):
    if ds==None:
        ds = pd.read_csv(path_to_output)
    df = pd.DataFrame(columns = ['id', 'item_id', 'true_bbox', 'prompt', 'correct', 'rejected', 
                             'iou_correct', 'score_correct', 'harmonic_correct',
                             'iou_rejected', 'score_rejected', 'harmonic_rejected', 'description_bbox'])
    object_descriptions = get_objects_descriptions(ds)
    for i in range(len(ds)):
        # try:
        if ds["score"][i]==-1:
            continue
        resp1 = ds['description'][i]
        prompt = "Paraphrase sentence: " + str(resp1)
        print(prompt)
        
        while True:     
            n1 = random.choice([k for k in range(0,len(object_descriptions[ds['item_id'][i]]))])
            if object_descriptions[ds['item_id'][i]][n1] != resp1:
                resp2 = object_descriptions[ds['item_id'][i]][n1][1]
                k1 = object_descriptions[ds['item_id'][i]][n1][0]
                break
        while True:     
            n2 = random.choice([k for k in range(0,len(object_descriptions[ds['item_id'][i]]))])
            if object_descriptions[ds['item_id'][i]][n2] != resp1 and object_descriptions[ds['item_id'][i]][n2] != resp2:
                k2 = object_descriptions[ds['item_id'][i]][n2][0]
                break
        
        if ds['harmonic_mean'][k1] >=  ds['harmonic_mean'][k2]:
            df.loc[len(df)] = [i, ds['item_id'][i], ds['true_bbox'][i], prompt, ds['description'][k1], ds['description'][k2],
                               ds['response_iou'][k1], ds['response_score'][k1], ds['harmonic_mean'][k1],
                              ds['response_iou'][k2], ds['response_score'][k2], ds['harmonic_mean'][k2], ds['description_bbox'][i]]
        else: 
            df.loc[len(df)] = [i, ds['item_id'][i], ds['true_bbox'][i], prompt, ds['description'][k2], ds['description'][k1],
                               ds['response_iou'][k2], ds['response_score'][k2], ds['harmonic_mean'][k2], 
                               ds['response_iou'][k1], ds['response_score'][k1], ds['harmonic_mean'][k1], ds['description_bbox'][i]]
        # except Exception as e: 
        #     print(e)
        #     continue
    df.to_csv(path_to_output, index=False)

def main():
    # Initialize the tokenizer, model and reference model
    parser = HfArgumentParser(ProcessingArguments)
    p_args = parser.parse_args_into_dataclasses()[0]
    model_name = p_args.model_name
    path_to_source = p_args.path_to_source
    path_to_imgs = p_args.path_to_imgs
    path_to_output = p_args.path_to_output
    ranking_strategy = p_args.ranking_strategy
    threshhold = p_args.ranking_strategy
    use_score = p_args.use_score


    ds = evaluate_descriptions(model_name, path_to_imgs, path_to_output, path_to_source,use_score,ranking_strategy,threshhold)
    generate_triplets(path_to_output)
# Generate text
if __name__ == "__main__":
    main()
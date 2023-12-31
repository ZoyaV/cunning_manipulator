from coco_dataset_handler import CocoWrapper
from detectors.owlvit import OwlViTDetector
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import matplotlib.patches as patches
from metrics.metrics import calculate_iou
from categories import category_dict
import tqdm
import torch
def plot_bbox(im, true_bbox, predicted_bbox):
    # Open the image
   # im = np.array(Image.open(image_path), dtype=np.uint8)

    # Create figure and axis
    fig, ax = plt.subplots(1)

    # Display the image
    ax.imshow(im)

    # Create a rectangle for the true bbox
    true_rect = patches.Rectangle((true_bbox[0], true_bbox[1]), true_bbox[2], true_bbox[3],
                                  linewidth=1, edgecolor='r', facecolor='none')

    # Create a rectangle for the predicted bbox
    predicted_rect = patches.Rectangle((predicted_bbox[0], predicted_bbox[1]), predicted_bbox[2], predicted_bbox[3],
                                       linewidth=1, edgecolor='b', facecolor='none')

    # Add the rectangles to the image
    ax.add_patch(true_rect)
    ax.add_patch(predicted_rect)

    plt.show()


def average_metric(manipulator = None, prompt_f = lambda x: f"A synonym for the word '{x}' is = "):
    if manipulator:
        manipulation_model, tokenizer = manipulator
    model = OwlViTDetector("google/owlvit-base-patch32")
    coco_wrapper = CocoWrapper('./dataset/result.json')
    iou_mean = []
    for i in tqdm.tqdm(range(1, 121)):

        image = coco_wrapper.get_image(image_id=i, image_folder_path='./dataset/imgs')
        for j in category_dict.keys():
            if manipulator is None:
                text_queries = [category_dict[j]]
            else:
                text_prompt = prompt_f(category_dict[j])
              #  print("Inp: ", text_prompt)
                prompt = tokenizer.encode(text_prompt)

                manipulator_responce = manipulation_model.generate(torch.from_numpy(np.array(prompt).reshape(1, -1)), top_k = 1,
                                                                   min_length =5, top_p = 1.0, do_sample = True)
                responce = "a " + tokenizer.decode(manipulator_responce.squeeze()).replace("<pad>", "").replace("</s>", "")
              #  print("Outp: ", responce)
               # print(responce)
                text_queries = [responce]
            predicted_bbox = model.get_bboxes(image, text_queries)[0][1].tolist()
            xs, ys, xend, yend = predicted_bbox
            predicted_bbox = [xs, ys, xend, yend]
            annotations = coco_wrapper.get_anns(image_id=i, category_id=j)
            for annotation in annotations:
                true_bbox = annotation['bbox']

              #  print(predicted_bbox, true_bbox)
                iou = calculate_iou(true_bbox, predicted_bbox)
                iou_mean.append(iou)
    return np.mean(iou_mean)

def main():

    coco_wrapper = CocoWrapper('./dataset/result.json')
    category = 27
    category_name = category_dict[category]
    # Get all annotations for the given image and category
    annotations = coco_wrapper.get_anns(image_id=1, category_id=category)
    # Get image by id
    image = coco_wrapper.get_image(image_id=1, image_folder_path='./dataset/imgs')

    text_queries = [category_name]
    try:
        model = OwlViTDetector("google/owlvit-base-patch32")
        predicted_bbox = (model.get_bboxes(image, text_queries)[0][1]).tolist()
        xs,ys,xend, yend = predicted_bbox
        predicted_bbox = [xs, ys, xend, yend]
        print(predicted_bbox)
    except IndexError:
        predicted_bbox = [100.0, 150.0, 200.0, 250.0]
        # Apply the function
    for annotation in annotations:
        true_bbox = annotation['bbox']
        iou = calculate_iou(true_bbox, predicted_bbox)
      #  print(f'IoU for the bbox = {iou}')
        plot_bbox(image, true_bbox, predicted_bbox)

        # Get pandas dataframe
   # df = coco_wrapper.to_pandas(keys=['id', 'file_name', 'bbox', 'category_id'])

   # print(df)

from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)

from trl import AutoModelForSeq2SeqLMWithValueHead

if __name__ == "__main__":
    #tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-base")
    #model = AutoModelForSeq2SeqLMWithValueHead.from_pretrained('google/flan-t5-base')
    tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-base")
    model = AutoModelForSeq2SeqLMWithValueHead.from_pretrained('ppo_tuning/checkpoints/manipulator_v1')

    tokenizer.pad_token = tokenizer.eos_token

    manipulator = model, tokenizer
    print(average_metric(manipulator))
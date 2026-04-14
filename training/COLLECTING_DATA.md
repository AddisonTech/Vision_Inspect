## Overview
Fine-tuning Vision_Inspect models requires a well-labeled dataset of images or videos for training. This guide outlines the steps to collect and prepare your data.

## Step 1 — Enable Frame Saving
To enable frame saving in Vision_Inspect, navigate to the settings menu and select "Frame Saving." Configure it to save frames during inspections. Ensure you have sufficient storage space.

## Step 2 — Collect Raw Frames
Run inspections with the configured frame-saving setting enabled. Accumulate a diverse set of images or videos that cover various scenarios relevant to your use case.

## Step 3 — Label with Bounding Boxes
Use tools like LabelImg or Roboflow for labeling. For bounding box annotations, ensure each object is accurately labeled and save the annotations in XML or JSON format.

## Step 4 — Convert to dataset_template.json Format
import json

def convert_to_json(annotations):
    dataset = {"data": []}
    for img_path, boxes in annotations.items():
        entry = {
            "image": img_path,
            "objects": []
        }
        for box in boxes:
            x_min, y_min, width, height = box
            entry["objects"].append({
                "label": "object_name",  # Replace with actual label
                "bbox": [x_min, y_min, x_min + width, y_min + height]
            })
        dataset["data"].append(entry)
    return json.dumps(dataset)

# Example usage
annotations = {
    "path/to/image1.jpg": [[50, 60, 200, 300], [400, 500, 150, 200]],
    "path/to/image2.jpg": [[100, 150, 300, 400]]
}

json_data = convert_to_json(annotations)
print(json_data)

## Step 5 — Run Fine-Tuning
Use the following command to fine-tune your model:
llamafactory-cli train --config llama_factory_qlora.yaml

## Step 6 — Register with Ollama and Activate
Create a new model using the `ollama create` command. After training, use the `/models/rollback` endpoint to activate your fine-tuned model:
ollama create --name my_fine_tuned_model --config llama_factory_qlora.yaml
curl -X POST http://localhost:8000/models/rollback -H "Authorization: Bearer <your_token>" -d '{"model_name": "my_fine_tuned_model"}'

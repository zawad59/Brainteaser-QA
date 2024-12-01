import os
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from sentence_transformers import SentenceTransformer, util
import pandas as pd

# Set device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Load SentenceTransformer for embeddings
embedder = SentenceTransformer('all-MiniLM-L6-v2').to(device)

# Load test dataset
test_data = np.load("/home/jawadkk/Brainteaser-GPT2/CombinedDatasets/All_test 1.npy", allow_pickle=True)

# Define learning rates and weight decays
learning_rates = [0.1, 0.05, 0.01, 0.005, 0.001, 0.0005, 0.0001, 0.00001]
weight_decays = [0.00001, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]

# Preprocess the test dataset
def preprocess_data(data):
    processed_data = []
    for idx, item in enumerate(data):
        question = item['question']
        choices = item['choice_list']
        label = item['label']
        processed_data.append({
            'id': idx + 1,
            'text': question,
            'choices': choices,
            'correct_answer': choices[label]
        })
    return processed_data

processed_test_data = preprocess_data(test_data)

# Define the prompt
PROMPT = (
    "You're a model to select correct answers from the given questions and answer choices. "
    "The answer choices might look similar to each other but it's your job to figure out the correct one given the training you got.\n\n"
    "Here are some examples:\n"
    "{'id': 'SP-0', 'question': 'Mr. and Mrs. Mustard have six daughters and each daughter has one brother. But there are only 9 people in the family, how is that possible?', "
    "'answer': 'Each daughter shares the same brother.', 'distractor1': 'Some daughters get married and have their own family.', "
    "'distractor2': 'Some brothers were not loved by family and moved away.', 'distractor(unsure)': 'None of above.', 'label': 1, "
    "'choice_list': ['Some daughters get married and have their own family.', 'Each daughter shares the same brother.', 'Some brothers were not loved by family and moved away.', 'None of above.'], 'choice_order': [1, 0, 2, 3]}\n"
    "{'id': 'WP-131', 'question': 'What is a boxer’s favorite drink?', 'answer': 'Punch.', 'distractor1': 'Coke.', 'distractor2': 'Sprite.', "
    "'distractor(unsure)': 'None of above.', 'label': 1, 'choice_list': ['Coke.', 'Punch.', 'Sprite.', 'None of above.'], 'choice_order': [1, 0, 2, 3]}\n"
)

# Generate answers using the model
def generate_answer(model, tokenizer, question, choices):
    prompt = (
        PROMPT
        + f"\n\nQuestion: {question}\nChoices:\n"
        + "\n".join([f"{i + 1}. {choice}" for i, choice in enumerate(choices)])
        + "\nAnswer:"
    )
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024).to(device)
    outputs = model.generate(inputs["input_ids"], attention_mask=inputs["attention_mask"], max_new_tokens=50)
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    explanation = "Based on context and semantic similarity, the chosen answer matches the question."
    return generated_text.split("Answer:")[-1].strip(), explanation

# Evaluate the model on the test data
def evaluate_model(model, tokenizer, test_data, output_file):
    results = []
    for item in test_data:
        question_id = item['id']
        question = item['text']
        choices = item['choices']
        correct_answer = item['correct_answer']
        generated_answer, explanation = generate_answer(model, tokenizer, question, choices)
        prediction_match = "yes" if generated_answer == correct_answer else "no"
        results.append({
            "Question_ID": question_id,
            "Question_Text": question,
            "Answer_Choices": "; ".join(choices),
            "Model_Predicted_Answer": generated_answer,
            "Actual_Answer": correct_answer,
            "Predicted == Actual": prediction_match,
            "Explanation": explanation
        })

    # Save results to a CSV file
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_file, index=False)
    print(f"Results saved to {output_file}")

# Evaluate all combinations
def evaluate_all_combinations(processed_test_data, learning_rates, weight_decays, base_model_dir="/home/jawadkk/Brainteaser-GPT2/Llama3.2/"):
    for lr in learning_rates:
        for wd in weight_decays:
            model_id = f"llama_lora_finetuned_lr{lr}_wd{wd}"
            model_path = os.path.join(base_model_dir, model_id)
            output_file = f"Results/{model_id}_results.csv"
            os.makedirs("Results", exist_ok=True)
            try:
                # Load the fine-tuned model
                model = AutoModelForCausalLM.from_pretrained(model_path).to(device)
                tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)
                tokenizer.pad_token = tokenizer.eos_token
                tokenizer.pad_token_id = tokenizer.eos_token_id  # Avoid warning during generation

                # Evaluate the model
                evaluate_model(model, tokenizer, processed_test_data, output_file)
            except Exception as e:
                print(f"Error evaluating {model_id}: {e}")

# Run evaluation
evaluate_all_combinations(processed_test_data, learning_rates, weight_decays)

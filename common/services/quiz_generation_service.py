# services/quiz_generation_service.py
import logging
import requests
import json
import uuid
from ..models import QuizQuestion  # Ensure you import your model (using relative import)
from .config_service import get_cached_config_by_key


logger = logging.getLogger(__name__)

def generate_quiz_questions(topic, difficulty, num_questions):
    """
    Calls the DeepSeek API to generate questions and saves them to the database.

    Args:
        topic (str): The topic of the questions.
        difficulty (str): The difficulty of the questions.
        num_questions (int): The number of questions.

    Returns:
        dict: A dictionary containing the generation_id, or an error message.
    """
    api_url = get_cached_config_by_key('api_url').value
    sk = get_cached_config_by_key('sk').value
    # api_url = "https://api.deepseek.com/chat/completions"
    generation_id = str(uuid.uuid4())  # Generate a unique batch ID

    # Construct the title
    title = f"Quiz on {topic} - {difficulty} - {num_questions} Questions"

    # Construct the Prompt
    # prompt = f"Please generate {num_questions} questions about {topic} with {difficulty} difficulty. Each question should include 4 options (labeled A, B, C, D), with one correct answer, and a concise explanation of why that answer is correct. The format should be: {{\"questions\": [{{\"question_text\": \"Question 1 content\", \"options\": {{\"A\": \"Option 1\", \"B\": \"Option 2\", \"C\": \"Option 3\", \"D\": \"Option 4\"}}, \"correct_answer\": \"Correct answer content\", \"correct_answer_explanation\": \"Concise explanation of why the correct answer is correct\"}}, ... ]}}. Do not add any extra text or explanations. Give me plain text, not markdown format."
    prompt = f"""
    Instructions: Please generate {num_questions} questions about {topic} with {difficulty} difficulty. Each question should include 4 options (labeled A, B, C, D), with one correct answer, and a concise explanation of why that answer is correct.
    Context: The questions are intended for a quiz system, and the target audience might be students or enthusiasts interested in the {topic} area.
    Input data: The number of questions to generate is {num_questions}, and the topic is {topic} with a difficulty level of {difficulty}.
    Output data: Provide the questions in the following JSON format: {{"questions": [{{"question_text": "Question 1 content", "options": {{"A": "Option 1", "B": "Option 2", "C": "Option 3", "D": "Option 4"}}, "correct_answer": "the right option(A or B or C or D)", "correct_answer_explanation": "Concise explanation of why the correct answer is correct"}}, ... ]}}. Do not add any extra text or explanations. Give me plain text, not markdown format.
    """

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a quiz system question generation assistant."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + sk  # Add Authorization header
    }

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Check for HTTP errors
        response_data = response.json()
        logger.log(logging.INFO, msg="payload:" + json.dumps(payload))
        logger.log(logging.INFO, msg="response_data: " + response_data)

        # Parse the JSON data
        content = response_data['choices'][0]['message']['content']
        try:
            quiz_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {content}")
            return {"error": f"JSON parsing error: {e}"}

        # Transform the data to use English keys
        transformed_questions = []
        for item in quiz_data.get('questions', []):
            transformed_question = {
                'question_text': item.get('question_text', ''),
                'options': item.get('options', {}),
                'correct_answer': item.get('correct_answer', ''),
                'correct_answer_explanation': item.get('correct_answer_explanation', '')  # Get the explanation
            }
            transformed_questions.append(transformed_question)

        # Save to the database
        for question_data in transformed_questions:
            QuizQuestion.objects.create(
                title=title,  # Save the title
                generation_id=generation_id,
                category=topic,
                difficulty=difficulty,
                question_text=question_data['question_text'],
                option_a=question_data['options']['A'],
                option_b=question_data['options']['B'],
                option_c=question_data['options']['C'],
                option_d=question_data['options']['D'],
                correct_answer=question_data['correct_answer'],
                correct_answer_explanation=question_data['correct_answer_explanation'],  # Save the explanation
            )

        return {"generation_id": generation_id}  # Return a dictionary containing the generation_id

    except requests.exceptions.RequestException as e:
        logger.error(f"API request error: {e}")
        return {"error": f"API request error: {e}"}
    except KeyError as e:
        logger.error(f"JSON structure error: Missing key {e}")
        return {"error": f"JSON structure error: Missing key {e}"}
    except Exception as e:
        logger.error(f"An unknown error occurred: {e}")
        return {"error": f"An unknown error occurred: {e}"}

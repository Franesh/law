import openai
import re
import spacy
from flask import Flask, request, render_template
import PyPDF2
from flask_sqlalchemy import SQLAlchemy


nlp = spacy.load("en_core_web_sm")

openai.api_key = "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"

# List of keywords related to Indian constitutional law
keywords = ["constitution", "law", "india", "article", "amendment", "supreme court", "parliament", "legislation"]

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(10))
    content = db.Column(db.String(500))


def extract_text_from_pdf(pdf_path):
    pdf_file_obj = open(pdf_path, 'rb')
    pdf_reader = PyPDF2.PdfFileReader(pdf_file_obj)
    text = ''
    for page_num in range(pdf_reader.numPages):
        page_obj = pdf_reader.getPage(page_num)
        text += page_obj.extractText()
    pdf_file_obj.close()
    return text


def is_legal_problem(question):
    doc = nlp(question)
    legal_entities = ["LAW", "COURT", "JUDGE", "JUSTICE", "CONSTITUTION"]
    return any(ent.label_ in legal_entities for ent in doc.ents)


def is_math_problem(question):
    return bool(re.search(r'\d', question)) and any(x in question for x in ['+', '-', '*', '/'])


def preprocess_data(data):
    # Add your preprocessing code here
    return data


def create_prompt(question, data, conversation_history):
    # Include relevant information from data in the prompt
    prompt = f"{data}\n{conversation_history}\n{question}"
    return prompt


def postprocess_response(response):
    # Remove unnecessary characters, format response, etc.
    processed_response = response.strip()
    # Define key phrases that indicate a new point
    key_phrases = ['Right to Privacy:', 'Right to live with dignity:', 'Right to speedy trial:', 'Right against custodial violence:', 'Right to fair trial:']
    # Split the response into points based on the key phrases
    points = re.split('|'.join(map(re.escape, key_phrases)), processed_response)
    # Remove any empty strings from the list
    points = [point for point in points if point]
    # Format each point as a list item with new numbering
    list_response = '\n'.join([f'{i+1}. {point}' for i, point in enumerate(points)])
    return list_response




def ask_gpt3(question, data, conversation_hidtory):
    preprocessed_data = preprocess_data(data)
    prompt = create_prompt(question, preprocessed_data, conversation_hidtory)
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": context},
            {"role": "user", "content": prompt}
        ]
    )

    processed_response = postprocess_response(response.choices[0].message['content'])
    return processed_response


context = "You are a knowledgeable assistant that specializes in Indian constitutional law."
app.secret_key = 'your secret key'  # Replace with your own secret key


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        question = request.form.get('question')
        conversation_history = "\n".join([msg.content for msg in Message.query.all()])
        response = ask_gpt3(question, context, conversation_history)
        db.session.add(Message(role="user", content=question))
        db.session.add(Message(role="bot", content=response))
        db.session.commit()
    else:  # This is a GET request
        Message.query.delete()  # Clear the message table
        db.session.commit()  # Commit the changes to the database
    messages = Message.query.all()
    return render_template('home.html', messages=messages)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True,host="0.0.0.0", port=8080)

import openai
import re
import spacy
from flask import Flask, request, render_template
import PyPDF2
from flask_sqlalchemy import SQLAlchemy
from googletrans import Translator
import requests
from bs4 import BeautifulSoup

nlp = spacy.load("en_core_web_sm")

openai.api_key = "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"

translator = Translator()

# List of keywords related to Indian constitutional law
keywords = ["constitution", "law", "acts", "animal act", "act", "india", "article", "IPC section", "amendment",
            "supreme court", "parliament", "legislation"]

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(10))
    content = db.Column(db.String(500))


def extract_text_from_pdf(pdf_path):
    text = "S.pdf"
    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text


def is_related_to_pdf(question, pdf_text):
    pdf_keywords = ["constitution", "law", "amendment", "supreme court", "IPC section", "parliament"]

    question = question.lower()
    pdf_text = pdf_text.lower()

    for keyword in pdf_keywords:
        if re.search(r'\b{}\b'.format(re.escape(keyword)), question) or re.search(r'\b{}\b'.format(re.escape(keyword)),
                                                                                  pdf_text):
            return True

    return False


def is_legal_problem(question):
    doc = nlp(question)
    legal_entities = ["LAW", "COURT", "JUDGE", "JUSTICE", "CONSTITUTION"]
    return any(ent.label_ in legal_entities for ent in doc.ents)


def is_math_problem(question):
    return bool(re.search(r'\d', question)) and any(x in question for x in ['+', '-', '*', '/'])


def preprocess_data(data):
    return data


def create_prompt(question, data, conversation_history):
    prompt = f"{data}\n{conversation_history}\n{question}"
    return prompt


def postprocess_response(response):
    processed_response = response.strip()
    key_phrases = ['Right to Privacy:', 'Right to live with dignity:', 'Right to speedy trial:',
                   'Right against custodial violence:', 'Right to fair trial:']
    points = re.split('|'.join(map(re.escape, key_phrases)), processed_response)
    points = [point for point in points if point]
    list_response = '\n'.join([f'{i + 1}. {point}' for i, point in enumerate(points)])
    return list_response


def is_programming_language_question(question):
    programming_languages = ["python", "java", "javascript", "c++", "ruby", "php", "swift", "html", "css", "sql"]
    for lang in programming_languages:
        if lang in question.lower():
            return True
    return False


def extract_keywords_from_website(url):
    # Make a GET request to the external website
    response = requests.get(url)
    # Parse the HTML content
    soup = BeautifulSoup(response.content, 'html.parser')
    # Extract specific keywords or relevant information from the website
    # Find all <div> elements with class "result_title"
    result_titles = soup.find_all('div', class_='result_title')
    # Extract text from result titles
    keywords = [title.text.strip() for title in result_titles]
    print("Extracted keywords:", keywords)  # Print extracted keywords
    return keywords


def ask_gpt3(question, context, conversation_history, pdf_text=None):
    # Check if the question is related to a PDF and there are specific keywords from the external website
    if is_related_to_pdf(question, pdf_text):
        # Extract specific keywords from the external website
        website_keywords = extract_keywords_from_website("https://blog.ipleaders.in/most-famous-controversial-criminal-cases-india/")
        # Create a prompt using the specific keywords from the website along with other context
        prompt = f"{context}\n{conversation_history}\nWebsite Information:\n{website_keywords}\nQuestion: {question}"
    else:
        # Create a prompt using only the context and conversation history
        prompt = f"{context}\n{conversation_history}\nQuestion: {question}"

    # Generate response from GPT-3 using the prompt
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": context},
            {"role": "user", "content": prompt}
        ]
    )

    processed_response = postprocess_response(response.choices[0].message['content'])
    return processed_response


context = ("You are a knowledgeable assistant that specializes in Indian constitutional law. Your task is to provide "
           "detailed information and answer questions strictly related to Indian constitutional law. Please refrain "
           "from discussing other topics.try to give case reference if user ask.if user ask like 'please give related case reference' please provide it . Dataset is only prepared for Indian constitutional law. Strictly don't give "
           "any information about programming codes like C, C++, Python, Java.")

app.secret_key = 'your secret key'


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        question = request.form.get('question')
        pdf_text = extract_text_from_pdf("S.pdf")
        conversation_history = "\n".join([msg.content for msg in Message.query.all()])
        response = ask_gpt3(question, pdf_text, context, conversation_history)
        db.session.add(Message(role="user", content=question))
        db.session.add(Message(role="bot", content=response))
        db.session.commit()
    else:
        Message.query.delete()
        db.session.commit()
    messages = Message.query.all()
    return render_template('home.html', messages=messages)


@app.route('/translate', methods=['POST'])
def translate_response():
    message_id = int(request.form.get('message_id'))
    message = db.session.get(Message, message_id)
    translated_content = translator.translate(message.content, dest='ta').text
    return translated_content


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

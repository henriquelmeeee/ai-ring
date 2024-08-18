from flask import Flask, render_template, request, g, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import time
import os


app = Flask(__name__, template_folder="./static", static_folder="./static")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

AIs = {
    0: "ChatGPT-4-Turbo",
    1: "Claude-3.5-Sonnet",
    2: "Llama-3.1-8B",
    3: "Llama-3.1-70B",
    4: "Llama-3.1-405B",
    5: "Llama-3-70B",
    6: "Llama-3-8B"
}

SUPPORTED_LANGUAGES = ["portuguese", "english"]

class Output(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    the_input = db.Column(db.String(50000), nullable=False)
    ai_id = db.Column(db.Integer, nullable=False)
    language = db.Column(db.String(20), nullable=False)

class AI(db.Model):
    name = db.Column(db.String(64), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100), nullable=False)
    portuguese_votes = db.Column(db.Integer, default=0)
    english_votes = db.Column(db.Integer, default=0)

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/<language>/")
def select_output(language):
    if language not in SUPPORTED_LANGUAGES:
        return "Invalid language", 400

    random_output_1 = Output.query.filter_by(language=language).order_by(db.func.random()).first()
    if not random_output_1:
        return "No outputs found for the specified language", 404
    print(f"Random output 1: {random_output_1}")
    print(f"Random output 1 details: id={random_output_1.id}, text={random_output_1.text}, input={random_output_1.the_input}, ai_id={random_output_1.ai_id}, language={random_output_1.language}")
    random_output_2 = Output.query.filter_by(language=language, the_input=random_output_1.the_input).filter(Output.id != random_output_1.id).order_by(db.func.random()).first()
    
    if not random_output_2:
        return "Not enough outputs for comparison", 404

    return render_template('compare.html', out1=random_output_1, out2=random_output_2)

@app.route("/select/<language_and_id>")
@limiter.limit("1 per 2 seconds")
def select_prefered(language_and_id):
    try:
        language, output_id = language_and_id.split("_")
        output_id = int(output_id)
    except ValueError:
        return "Invalid input format", 400

    if language not in SUPPORTED_LANGUAGES:
        return "Invalid language", 400

    output = Output.query.get(output_id)
    if not output:
        return "Output not found", 404

    ai = AI.query.get(output.ai_id)
    if not ai:
        return "AI not found", 404

    if language == "portuguese":
        ai.portuguese_votes += 1
    elif language == "english":
        ai.english_votes += 1

    db.session.commit()

    return AIs[ai.id], 200

def format_number(num):
    if num < 1000:
        return str(num)
    elif num < 1000000:
        return f"{num/1000:.1f}k".rstrip('0').rstrip('.')
    elif num < 1000000000:
        return f"{num/1000000:.1f}m".rstrip('0').rstrip('.')
    else:
        return f"{num/1000000000:.1f}b".rstrip('0').rstrip('.')

from sqlalchemy import case, func

@app.route("/statistics/")
def statistics():
    stats = db.session.query(
        AI.id,
        AI.name,
        AI.english_votes,
        AI.portuguese_votes,
        (AI.english_votes + AI.portuguese_votes).label('total_votes')
    ).order_by((AI.english_votes + AI.portuguese_votes).desc()).all()

    formatted_stats = []
    for ai in stats:
        formatted_stats.append({
            'id': ai.id,
            'name': ai.name,
            'english_votes': format_number(ai.english_votes),
            'portuguese_votes': format_number(ai.portuguese_votes),
            'total_votes': format_number(ai.total_votes)
        })

    return render_template('statistics.html', stats=formatted_stats)

def init_db():
    db.create_all()
    if not Output.query.first():
        #db.session.add(Output(id=1, text='teste1', the_input='input1', ai_id=1, language='portuguese'))
        #db.session.add(Output(id=2, text='teste2', the_input='input1', ai_id=2, language='portuguese'))
        #db.session.commit()
        pass
    if not AI.query.first():
        for ai_id, ai_name in AIs.items():
            db.session.add(AI(id=ai_id, description="aa", name=ai_name))
        db.session.commit()

admin_mode=True

@app.route('/admin/')
def add_entry_form():
    if admin_mode:
        return render_template('admin.html')

@app.route('/add_entry', methods=['POST'])
def add_entry():
    language = request.form['language']
    input_text = request.form['input']
    ai_id = int(request.form['ai'])
    output_text = request.form['output']

    if language not in SUPPORTED_LANGUAGES:
        return "Invalid language", 400

    new_entry = Output(text=output_text, the_input=input_text, ai_id=ai_id, language=language)
    db.session.add(new_entry)
    db.session.commit()

    return redirect("/admin/")

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')

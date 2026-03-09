from flask import Flask, render_template, request, session, redirect, url_for
import pandas as pd
import random
import os
import re

###DELET
import pandas as pd
import re

csv_path = "nhs_drug_prices_cleaned_corrected.csv"   # change to your CSV filename

df = pd.read_csv(csv_path)

# Remove spaces before "/" in dose_info column
df["dose_info"] = df["dose_info"].astype(str).str.replace(r"\s+\/", "/", regex=True)

# Save back to the same file
df.to_csv(csv_path, index=False)
###DELET

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # needed for session

# Load dataset
df = pd.read_csv("nhs_drug_prices_cleaned_corrected.csv")
df['price_pound'] = df['price_pound'].astype(float)

# Create mapping: cleaned drug_form_game_icon_list -> icon filename
icon_lookup = {
    str(key).lower().strip(): str(value).strip()
    for key, value in zip(df["drug_form_game_icon_list"], df["icon"])
    if pd.notna(key) and pd.notna(value)
}

# --------------------------
# Pick a new drug
# --------------------------
def pick_new_drug():
    row = df.sample(n=1).iloc[0]
    session["drug_name"] = row["drug_name"]
    session["drug_form"] = row["drug_form"]
    session["drug_form_description"] = row.get("drug_form_description", "")  # NEW
    session["total_pack_size"] = row.get("total_pack_size", "")  # NEW
    session["correct_price"] = row["price_pound"]
    session["guesses_left"] = 5
    session["last_feedback"] = ""
    session["game_over"] = False
    session["guess_history"] = []
    session["clue_description"] = row.get("clue_description", "")
    session["dose_info"] = row["dose_info"]  # whatever your CSV row dict is
    session["show_clue"] = False  # initially, clue not shown


# --------------------------
# Get drug_form image
# --------------------------

def get_image_filename(drug_form):
    # Handle missing / NaN
    if pd.isna(drug_form):
        return "default.png"

    # Convert to string, lowercase, strip spaces and newlines
    drug_form_clean = str(drug_form).lower().strip()

    # Remove all non-alphanumeric characters except underscore
    drug_form_clean = re.sub(r'[^a-z0-9_]', '', drug_form_clean)

    # Build filename
    filename = drug_form_clean + ".png"
    image_path = os.path.join("static", "images", filename)

    # Check if file exists
    if os.path.exists(image_path):
        return filename
    else:
        # Debug print for missing images
        print(f"DEBUG: Could not find image for '{drug_form}' -> tried '{filename}'")
        return "default.png"


# --------------------------
# Get drug_name image (robust)
# --------------------------
def get_drug_name_image_filename(drug_name):
    """
    Returns the image filename for drug_name.
    Looks inside static/images/drug_images/
    Falls back to default.png if missing.
    """
    if pd.isna(drug_name):
        return "default.png"

    # Clean the drug_name: lowercase, strip spaces/newlines, remove punctuation
    drug_name_clean = re.sub(r'[^a-z0-9_]', '', str(drug_name).lower().strip())
    filename = drug_name_clean + ".png"

    # New path inside drug_images folder
    image_path = os.path.join("static", "images", "drug_images", filename)

    if os.path.exists(image_path):
        return filename
    else:
        print(f"DEBUG: Could not find drug_name image for '{drug_name}' -> tried '{filename}'")
        return "default.png"
# --------------------------
# Get icon based on drug_form_description
# --------------------------
def get_icon_filename(drug_form_description):
    """
    Returns icon filename based on drug_form_description.
    Looks in static/images/icons/
    Falls back to default.png if missing.
    """
    if pd.isna(drug_form_description):
        return "default.png"

    # Clean description
    key = str(drug_form_description).lower().strip()

    # Find matching icon name
    icon_name = icon_lookup.get(key)

    if not icon_name:
        print(f"DEBUG: No icon match for '{drug_form_description}'")
        return "default.png"

    filename = icon_name + ".png"
    image_path = os.path.join("static", "images", "icons", filename)

    if os.path.exists(image_path):
        return filename
    else:
        print(f"DEBUG: Icon file not found: {filename}")
        return "default.png"

# --------------------------
# Feedback colour
# --------------------------
def get_feedback_color(correct_price, guess, result_text):
    percent_diff = abs(correct_price - guess) / correct_price

    # Winning guess
    if result_text == "Correct":
        return "rgb(40,167,69)"  # green

    # Within 20%
    elif percent_diff <= 0.20:
        return "rgb(255,193,7)"  # yellow

    # More than 20%
    else:
        return "rgb(220,53,69)"  # red


# --------------------------
# Main route
# --------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "drug_name" not in session or "drug_form" not in session:
        pick_new_drug()

    if "game_over" not in session:
        session["game_over"] = False

    if request.method == "POST":

        # New game should ALWAYS work
        if "new_game" in request.form:
            pick_new_drug()
            return redirect(url_for("index"))

        # -----------------------------
        # Hint button logic goes here
        # -----------------------------
        if "hint" in request.form:
            # Only show clue if not already shown
            if not session.get("show_clue", False):
                session["show_clue"] = True

                # Only consume a guess if more than 1 guess left
                if session["guesses_left"] > 1:
                    session["guesses_left"] -= 1

                # Add hint placeholder to guess history
                history = session.get("guess_history", [])
                history.append({
                    "guess": "HINT USED",
                    "result": "",
                    "arrow": "",
                    "color": "#6c757d"  # grey for hint
                })
                session["guess_history"] = history

            return redirect(url_for("index"))

        # Block further guesses if game finished
        if session.get("game_over"):
            session["show_clue"] = True
            return redirect(url_for("index"))

        # -----------------------------
        # Guess processing
        # -----------------------------
        guess_str = request.form.get("guess")
        try:
            guess = float(guess_str)
            if guess <= 0:
                session["last_feedback"] = "Enter a value greater than 0"
                return redirect(url_for("index"))

            session["guesses_left"] -= 1
            correct_price = session["correct_price"]

            result_text = ""
            # Calculate percentage difference
            percent_diff = abs(guess - correct_price) / correct_price

            if percent_diff <= 0.05:  # Within ±5% triggers win
                result_text = "Correct"
                color = get_feedback_color(correct_price, guess, result_text)
                session["last_feedback"] = f"CORRECT!\nThe actual price was £{correct_price:.2f}"
                session["feedback_color"] = "rgb(40,167,69)"  # green
                session["game_over"] = True
            elif guess < correct_price:
                result_text = "Higher"
                color = get_feedback_color(correct_price, guess, result_text)
            else:
                result_text = "Lower"
                color = get_feedback_color(correct_price, guess, result_text)

            # Save to guess history
            history = session.get("guess_history", [])
            if result_text == "Higher":
                arrow = "↑"
            elif result_text == "Lower":
                arrow = "↓"
            elif result_text == "Correct":
                arrow = "✓"
            else:
                arrow = ""

            history.append({
                "guess": round(guess, 2),
                "result": result_text,
                "arrow": arrow,
                "color": color
            })
            session["guess_history"] = history

            # Check if out of guesses
            if session["guesses_left"] == 0 and not session["game_over"]:
                session["last_feedback"] = f"Out of guesses!\nCorrect price: £{correct_price:.2f}"
                session["feedback_color"] = "rgb(220,53,69)"
                session["game_over"] = True

        except:
            session["last_feedback"] = "Please enter a valid number"
            session["feedback_color"] = "rgb(0,0,0)"

        return redirect(url_for("index"))

    # Get images for display
    drug_form_description = session.get("drug_form_description", None)
    form_image_file = get_icon_filename(drug_form_description)

    drug_name_value = session.get("drug_name", None)
    name_image_file = get_drug_name_image_filename(drug_name_value)

    return render_template(
        "index.html",
        drug_name=session["drug_name"].upper(),
        drug_form=session["drug_form"].upper(),
        drug_form_description=session.get("drug_form_description", ""),
        dose_info=session.get("dose_info", ""),
        total_pack_size=session.get("total_pack_size", ""),
        clue_description=session.get("clue_description", ""),
        show_clue=session.get("show_clue", False),
        guesses_left=session["guesses_left"],
        last_feedback=session.get("last_feedback", ""),
        feedback_color=session.get("feedback_color", "black"),
        game_over=session.get("game_over", False),
        form_image_file=form_image_file,
        name_image_file=name_image_file,
        guess_history=session.get("guess_history", []),
        max_guesses=session.get("max_guesses", 5),
        correct_price = session["correct_price"]
    )

if __name__ == "__main__":
    app.run(debug=True)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
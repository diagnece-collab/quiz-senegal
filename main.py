import flet as ft
from flet.fastapi import app as flet_app  # Correction pour le déploiement
from fastapi import FastAPI
from pydantic import BaseModel
import sqlite3
import random
import json
import os
from typing import List
import uvicorn

# --- INITIALISATION DU SERVEUR ---
app = FastAPI()

# --- MODÈLE DE DONNÉES & BASE ---
class ScoreEntry(BaseModel):
    pseudo: str
    score: int

def init_db():
    conn = sqlite3.connect("scores.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pseudo TEXT NOT NULL,
            score INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- ROUTES BACKEND (Conservées à l'identique) ---

@app.get("/leaderboard", response_model=List[ScoreEntry])
def get_leaderboard_api():
    try:
        conn = sqlite3.connect("scores.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT pseudo, score FROM leaderboard ORDER BY score DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        return [{"pseudo": r[0], "score": r[1]} for r in rows]
    except:
        return []

@app.post("/add_score")
def add_score_api(entry: ScoreEntry):
    try:
        conn = sqlite3.connect("scores.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO leaderboard (pseudo, score) VALUES (?, ?)", (entry.pseudo, entry.score))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- INTERFACE FLET (Ton code exact, sans pollution) ---

def main(page: ft.Page):
    SENEGAL_VERT = "#00853f"
    SENEGAL_JAUNE = "#fdef42"
    SENEGAL_ROUGE = "#e31b23"

    page.title = "Conseil des Sages - Web"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 30
    page.bgcolor = "#121212"
    page.vertical_alignment = "center"
    page.horizontal_alignment = "center"

    state = {
        "pseudo": "Anonyme",
        "mode": None, 
        "idx": 0, 
        "score": 0, 
        "questions_partie": [],
        "erreurs_commises": [], 
        "leaderboard": []
    }

    # Communication simplifiée pour la production (Direct DB)
    def recuperer_classement():
        state["leaderboard"] = get_leaderboard_api()

    def envoyer_score_au_serveur():
        if state["mode"] == "SOLO":
            add_score_api(ScoreEntry(pseudo=state["pseudo"], score=state["score"]))

    def charger_questions():
        nom_fichier = "questions.json"
        if os.path.exists(nom_fichier):
            try:
                with open(nom_fichier, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    banque_complete = charger_questions()

    # --- UI ELEMENTS ---
    txt_diagnostic = ft.Text("", color="grey", size=14)
    txt_question = ft.Text("", size=22, weight="bold", text_align="center")
    container_question = ft.Container(
        content=txt_question, padding=20, border_radius=15, 
        bgcolor="#1E1E1E", border=ft.border.all(1, "#333333")
    )
    col_btns = ft.Column(alignment="center", spacing=15)
    progress_bar = ft.Row([
        ft.Container(expand=1, height=6, bgcolor=SENEGAL_VERT, border_radius=5), 
        ft.Container(expand=1, height=6, bgcolor=SENEGAL_JAUNE, border_radius=5), 
        ft.Container(expand=1, height=6, bgcolor=SENEGAL_ROUGE, border_radius=5)
    ], spacing=5)

    def update_ui_question():
        if not state["questions_partie"]: return
        q = state["questions_partie"][state["idx"]]
        opts = list(q["options"])
        random.shuffle(opts)
        txt_diagnostic.value = f"DIAGNOSTIC {state['idx']+1}/{len(state['questions_partie'])}"
        txt_question.value = q["q"]
        col_btns.controls.clear()
        for opt in opts:
            col_btns.controls.append(
                ft.Container(
                    content=ft.ElevatedButton(
                        content=ft.Text(opt, color="white", size=16),
                        style=ft.ButtonStyle(bgcolor=SENEGAL_VERT, shape=ft.RoundedRectangleBorder(radius=10), padding=20),
                        on_click=lambda e, v=opt: handle_answer(v)
                    ), width=500
                )
            )
        page.update()

    def handle_answer(choix):
        question_actuelle = state["questions_partie"][state["idx"]]
        if choix == question_actuelle["reponse"]:
            state["score"] += 1
        else:
            state["erreurs_commises"].append({
                "q": question_actuelle["q"],
                "votre_reponse": choix,
                "la_verite": question_actuelle["reponse"],
                "explication": question_actuelle.get("explication", "La vérité est établie par le Conseil.")
            })
        state["idx"] += 1
        if state["idx"] < len(state["questions_partie"]):
            update_ui_question()
        else:
            show_verdict()

    def show_verdict():
        envoyer_score_au_serveur()
        page.clean()
        total = len(state["questions_partie"])
        admis = (state["score"] / total) >= 0.75 if total > 0 else False
        color = SENEGAL_VERT if admis else SENEGAL_ROUGE

        col_erreurs = ft.Column(spacing=10, scroll=ft.ScrollMode.ALWAYS, height=250)
        for err in state["erreurs_commises"]:
            col_erreurs.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"Question : {err['q']}", size=14, weight="bold"),
                        ft.Text(f"Vous avez dit : {err['votre_reponse']}", color=SENEGAL_ROUGE, size=12),
                        ft.Text(f"La réponse était : {err['la_verite']}", color=SENEGAL_VERT, size=12, weight="bold"),
                        ft.Text(f"Note : {err['explication']}", italic=True, size=11, color="grey"),
                    ], spacing=3),
                    padding=15, bgcolor="#1A1A1A", border_radius=10, border=ft.border.all(1, "#333333")
                )
            )

        page.add(
            ft.Column([
                ft.Icon(ft.Icons.GAVEL_ROUNDED, color=color, size=80),
                ft.Text("VERDICT SOUVERAIN", size=36, weight="bold"),
                ft.Text(f"Citoyen {state['pseudo']}, votre score : {state['score']}/{total}", size=20, color="grey"),
                ft.Divider(height=20, color="transparent"),
                ft.Container(
                    content=ft.Text("ADMIS AU VOTE" if admis else "CAPACITÉ REJETÉE", color="white", weight="bold", size=20),
                    bgcolor=color, padding=25, border_radius=15, shadow=ft.BoxShadow(blur_radius=15, color=color)
                ),
                ft.Divider(height=20, color="transparent"),
                col_erreurs if state["erreurs_commises"] else ft.Text("Parfait !", color=SENEGAL_VERT),
                ft.TextButton("Voir le classement", on_click=lambda _: afficher_menu_principal(), style=ft.ButtonStyle(color=SENEGAL_JAUNE))
            ], horizontal_alignment="center", scroll=ft.ScrollMode.ADAPTIVE)
        )
        page.update()

    def start_game(pseudo_input):
        if not pseudo_input.value:
            pseudo_input.error_text = "Le Conseil exige un nom"
            page.update()
            return
        state["pseudo"] = pseudo_input.value
        state["erreurs_commises"] = []
        state.update({"mode": "SOLO", "idx": 0, "score": 0, "questions_partie": random.sample(banque_complete, min(len(banque_complete), 20))})
        page.clean()
        page.add(ft.Column([progress_bar, txt_diagnostic, container_question, col_btns], horizontal_alignment="center"))
        update_ui_question()

    def afficher_menu_principal():
        page.clean()
        recuperer_classement()
        pseudo_field = ft.TextField(label="Votre Pseudo", width=350, border_color=SENEGAL_JAUNE)
        
        leaderboard_list = ft.Column([
            ft.Text("TOP 10 DES SAGES", weight="bold", size=18, color=SENEGAL_JAUNE),
            ft.Divider(color=SENEGAL_JAUNE)
        ], horizontal_alignment="center")
        
        for i, entry in enumerate(state["leaderboard"]):
            leaderboard_list.controls.append(
                ft.Row([
                    ft.Text(f"{i+1}.", width=30, color=SENEGAL_JAUNE),
                    ft.Text(entry['pseudo'], expand=True),
                    ft.Text(f"{entry['score']} pts", color=SENEGAL_VERT)
                ], width=300)
            )

        page.add(
            ft.Image(src="https://upload.wikimedia.org/wikipedia/commons/thumb/f/fd/Flag_of_Senegal.svg/1200px-Flag_of_Senegal.svg.png", width=100),
            ft.Text("CONSEIL DES SAGES", size=32, weight="bold", color=SENEGAL_JAUNE),
            pseudo_field,
            ft.ElevatedButton("ENTRER DANS LE CONSEIL", width=350, on_click=lambda _: start_game(pseudo_field), style=ft.ButtonStyle(bgcolor=SENEGAL_VERT)),
            ft.Container(content=leaderboard_list, padding=25, bgcolor="#1E1E1E", border_radius=15, width=380)
        )
        page.update()

    afficher_menu_principal()

# --- MONTAGE (Version simplifiée pour Render) ---
app.mount("/", flet_app(main))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
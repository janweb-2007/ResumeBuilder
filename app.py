import os
import re
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
from PIL import Image, ImageTk

from db import (create_tables, sign_up, login, save_resume, get_my_resumes,
                get_resume, update_resume, delete_resume)
from output import build_preview_text, completeness, ats_score, export_pdf, STOPWORDS

LIGHT = {"bg": "#eef2f8", "card": "#ffffff", "fg": "#111827", "muted": "#64748b",
         "entry": "#f1f5f9", "border": "#dbe3ef", "accent": "#4f46e5", "hover": "#4338ca",
         "accent2": "#06b6d4", "good": "#16a34a", "warn": "#d97706", "bad": "#dc2626"}
DARK = {"bg": "#0f172a", "card": "#1e293b", "fg": "#e2e8f0", "muted": "#94a3b8",
        "entry": "#334155", "border": "#3b4a63", "accent": "#6366f1", "hover": "#4f46e5",
        "accent2": "#22d3ee", "good": "#4ade80", "warn": "#fbbf24", "bad": "#f87171"}

AVATAR_COLORS = ["#6366f1", "#0891b2", "#db2777", "#ea580c", "#16a34a", "#9333ea"]

SECTIONS = [("Summary", "summary"), ("Education", "education"), ("Skills", "skills"),
            ("Experience", "experience"), ("Projects", "projects")]
BULLET_KEYS = {"education", "experience", "projects"}

TEMPLATE_INFO = {
    "Classic": "Centered name, serif font, colored headings with lines",
    "Modern": "Left aligned, clean sans font, accent lines",
    "Minimal": "Plain black text, no lines, very clean",
}

state = {"user_id": None, "username": "", "dark": False, "color": "#4f46e5", "photo": "",
         "editing_id": None, "editor_resume": None, "draft": None, "form_getter": None,
         "redraw": None, "save_fn": None, "list_rows": [], "thumb": None}


def theme():
    return DARK if state["dark"] else LIGHT


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    a = hex_to_rgb(c1)
    b = hex_to_rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


root = tk.Tk()
root.title("Resume Builder")
root.geometry("1180x760")
root.minsize(1000, 680)
root.configure(bg=LIGHT["bg"])

style = ttk.Style()
style.theme_use("clam")

container = tk.Frame(root)
container.pack(fill="both", expand=True)


def apply_styles():
    t = theme()
    style.configure("TNotebook", background=t["card"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=[16, 8], background=t["entry"], foreground=t["muted"],
                    font=("Segoe UI", 10, "bold"), borderwidth=0)
    style.map("TNotebook.Tab", background=[("selected", t["accent"])],
              foreground=[("selected", "#ffffff")])
    style.configure("TCombobox", fieldbackground=t["entry"], background=t["entry"],
                    foreground=t["fg"], arrowcolor=t["fg"], bordercolor=t["border"])
    style.map("TCombobox", fieldbackground=[("readonly", t["entry"])],
              foreground=[("readonly", t["fg"])])
    style.configure("Accent.Horizontal.TProgressbar", troughcolor=t["border"], background=t["accent"],
                    bordercolor=t["border"], lightcolor=t["accent"], darkcolor=t["accent"], thickness=10)
    style.configure("Vertical.TScrollbar", background=t["entry"], troughcolor=t["bg"],
                    bordercolor=t["bg"], arrowcolor=t["fg"])


def clear():
    for w in container.winfo_children():
        w.destroy()
    t = theme()
    root.configure(bg=t["bg"])
    container.configure(bg=t["bg"])
    state["save_fn"] = None
    apply_styles()


def make_label(parent, text, size=11, bold=False, muted=False, wrap=None):
    t = theme()
    return tk.Label(parent, text=text, bg=parent["bg"], fg=t["muted"] if muted else t["fg"],
                    font=("Segoe UI", size, "bold" if bold else "normal"),
                    wraplength=wrap or 0, justify="left")


def make_entry(parent, width=40, show=None, textvariable=None):
    t = theme()
    return tk.Entry(parent, width=width, bg=t["entry"], fg=t["fg"], insertbackground=t["fg"],
                    relief="flat", bd=0, font=("Segoe UI", 11), show=show, textvariable=textvariable,
                    highlightthickness=1, highlightbackground=t["border"], highlightcolor=t["accent"])


def make_text(parent, height=6):
    t = theme()
    return tk.Text(parent, height=height, width=50, wrap="word", bg=t["entry"], fg=t["fg"],
                   insertbackground=t["fg"], relief="flat", bd=0, font=("Segoe UI", 10),
                   padx=10, pady=8, highlightthickness=1, highlightbackground=t["border"],
                   highlightcolor=t["accent"])


def make_button(parent, text, command, kind="primary"):
    t = theme()
    if kind == "primary":
        bg, fg, hover = t["accent"], "#ffffff", t["hover"]
    elif kind == "danger":
        bg, fg, hover = t["bad"], "#ffffff", "#b91c1c"
    else:
        bg, fg, hover = t["entry"], t["fg"], t["border"]
    btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=hover,
                    activeforeground=fg, relief="flat", bd=0, padx=14, pady=7,
                    font=("Segoe UI", 10, "bold"), cursor="hand2")
    btn.bind("<Enter>", lambda e: btn.config(bg=hover))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def card(parent):
    t = theme()
    return tk.Frame(parent, bg=t["card"], highlightbackground=t["border"], highlightthickness=1, bd=0)


def gradient_strip(parent):
    strip = tk.Canvas(parent, height=5, highlightthickness=0, bd=0, bg=theme()["bg"])

    def paint(event=None):
        t = theme()
        strip.delete("all")
        w = strip.winfo_width()
        steps = 100
        for i in range(steps):
            x0 = w * i / steps
            x1 = w * (i + 1) / steps + 1
            c = mix(t["accent"], t["accent2"], i / (steps - 1))
            strip.create_rectangle(x0, 0, x1, 5, fill=c, outline=c)

    strip.bind("<Configure>", paint)
    return strip


def toggle_dark():
    if state["form_getter"]:
        state["draft"] = state["form_getter"]()
    state["dark"] = not state["dark"]
    state["redraw"]()


def logout():
    state.update({"user_id": None, "username": "", "editing_id": None, "editor_resume": None,
                  "form_getter": None, "draft": None})
    show_login()


def header(title, subtitle="", back=None):
    t = theme()
    bar = tk.Frame(container, bg=t["card"])
    bar.pack(fill="x")
    inner = tk.Frame(bar, bg=t["card"])
    inner.pack(fill="x", padx=28, pady=14)
    left = tk.Frame(inner, bg=t["card"])
    left.pack(side="left")
    if back:
        make_button(left, "Back", back, "ghost").pack(side="left", padx=(0, 16))
    titles = tk.Frame(left, bg=t["card"])
    titles.pack(side="left")
    make_label(titles, title, 17, True).pack(anchor="w")
    if subtitle:
        make_label(titles, subtitle, 10, muted=True).pack(anchor="w")
    right = tk.Frame(inner, bg=t["card"])
    right.pack(side="right")
    make_button(right, "Light mode" if state["dark"] else "Dark mode", toggle_dark, "ghost").pack(side="right")
    if state["user_id"]:
        make_button(right, "Logout", logout, "ghost").pack(side="right", padx=8)
    gradient_strip(container).pack(fill="x")


def toast(message, kind="good"):
    t = theme()
    label = tk.Label(root, text=message, bg=t[kind], fg="#ffffff", font=("Segoe UI", 10, "bold"),
                     padx=20, pady=10)
    label.place(relx=0.5, rely=0.97, anchor="s")
    root.after(2200, label.destroy)


def validate(data):
    if not data["name"]:
        return "Full name is required."
    if not data["phone"]:
        return "Phone number is required."
    if len(re.sub(r"\D", "", data["phone"])) < 10:
        return "Phone number must have at least 10 digits."
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", data["email"]):
        return "Enter a valid email, like name@gmail.com."
    return None


def avatar(parent, name, size=46):
    initials = "".join(p[0] for p in name.split()[:2]).upper() or "?"
    color = AVATAR_COLORS[sum(ord(ch) for ch in name) % len(AVATAR_COLORS)]
    cv = tk.Canvas(parent, width=size, height=size, bg=parent["bg"], highlightthickness=0, bd=0)
    cv.create_oval(2, 2, size - 2, size - 2, fill=color, outline="")
    cv.create_text(size / 2, size / 2, text=initials, fill="#ffffff", font=("Segoe UI", 12, "bold"))
    return cv


def scroll_area():
    t = theme()
    holder = tk.Frame(container, bg=t["bg"])
    holder.pack(fill="both", expand=True, padx=22, pady=(4, 12))
    canvas = tk.Canvas(holder, bg=t["bg"], highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=sb.set)
    inner = tk.Frame(canvas, bg=t["bg"])
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

    def wheel(e):
        if canvas.winfo_exists():
            canvas.yview_scroll(int(-e.delta / 120), "units")

    canvas.bind_all("<MouseWheel>", wheel)
    return inner


def stat_card(parent, label, value, color):
    c = card(parent)
    c.pack(side="left", fill="x", expand=True, padx=6)
    body = tk.Frame(c, bg=c["bg"])
    body.pack(fill="both", expand=True, padx=18, pady=12)
    tk.Label(body, text=value, bg=c["bg"], fg=color, font=("Segoe UI", 18, "bold")).pack(anchor="w")
    make_label(body, label, 9, muted=True).pack(anchor="w")


def duplicate(row):
    data = dict(row)
    data["name"] = f"{row['name'] or 'Untitled'} (Copy)"
    save_resume(state["user_id"], data)
    show_dashboard()
    toast("Resume duplicated", "accent")


def delete(row):
    if messagebox.askyesno("Delete", f"Delete '{row['name'] or 'Untitled'}'? This cannot be undone."):
        delete_resume(row["id"], state["user_id"])
        show_dashboard()
        toast("Resume deleted", "bad")


def resume_card(parent, r):
    t = theme()
    c = card(parent)
    c.pack(fill="x", pady=6, padx=6)
    c.bind("<Enter>", lambda e: c.config(highlightbackground=t["accent"]))
    c.bind("<Leave>", lambda e: c.config(highlightbackground=t["border"]))
    avatar(c, r["name"] or "Untitled").pack(side="left", padx=(18, 14), pady=16)
    info = tk.Frame(c, bg=t["card"])
    info.pack(side="left", fill="x", expand=True)
    make_label(info, r["name"] or "Untitled", 13, True).pack(anchor="w")
    pct = completeness(r)
    make_label(info, f"{r['template'] or 'Classic'}  |  {pct}% complete  |  Resume ID {r['id']}",
               9, muted=True).pack(anchor="w", pady=(2, 0))
    actions = tk.Frame(c, bg=t["card"])
    actions.pack(side="right", padx=18)
    make_button(actions, "Open", lambda row=r: show_editor(row)).pack(side="left", padx=4)
    make_button(actions, "Duplicate", lambda row=r: duplicate(row), "ghost").pack(side="left", padx=4)
    make_button(actions, "Delete", lambda row=r: delete(row), "danger").pack(side="left", padx=4)


def show_login():
    clear()
    state.update({"redraw": show_login, "form_getter": None})
    t = theme()
    header("Resume Builder", "Create polished resumes in minutes")
    body = tk.Frame(container, bg=t["bg"])
    body.pack(fill="both", expand=True)
    box = card(body)
    box.pack(expand=True, ipadx=36, ipady=26)

    make_label(box, "Welcome back", 18, True).pack(pady=(4, 2))
    make_label(box, "Log in to continue building your resume", 10, muted=True).pack(pady=(0, 18))
    make_label(box, "Username", 10, True).pack(anchor="w")
    user_entry = make_entry(box, 34)
    user_entry.pack(anchor="w", ipady=6, pady=(4, 12))
    make_label(box, "Password", 10, True).pack(anchor="w")
    pass_entry = make_entry(box, 34, show="*")
    pass_entry.pack(anchor="w", ipady=6, pady=(4, 6))
    show_var = tk.BooleanVar(value=False)
    tk.Checkbutton(box, text="Show password", variable=show_var,
                   command=lambda: pass_entry.config(show="" if show_var.get() else "*"),
                   bg=t["card"], fg=t["muted"], selectcolor=t["card"], activebackground=t["card"],
                   activeforeground=t["fg"], font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 16))

    def do_login():
        username = user_entry.get().strip()
        password = pass_entry.get()
        if not username or not password:
            messagebox.showerror("Login", "Enter both username and password.")
            return
        user_id = login(username, password)
        if user_id is None:
            messagebox.showerror("Login", "Wrong username or password.")
            return
        state.update({"user_id": user_id, "username": username})
        show_dashboard()

    user_entry.bind("<Return>", lambda e: pass_entry.focus_set())
    pass_entry.bind("<Return>", lambda e: do_login())
    make_button(box, "Log in", do_login).pack(fill="x", ipady=3)
    make_button(box, "Create new account", show_signup, "ghost").pack(fill="x", pady=(10, 0))
    user_entry.focus_set()


def show_signup():
    clear()
    state.update({"redraw": show_signup, "form_getter": None})
    t = theme()
    header("Create account", "Takes 10 seconds. Your resumes stay private to you.", back=show_login)
    body = tk.Frame(container, bg=t["bg"])
    body.pack(fill="both", expand=True)
    box = card(body)
    box.pack(expand=True, ipadx=36, ipady=26)

    make_label(box, "Username (3+ characters)", 10, True).pack(anchor="w")
    user_entry = make_entry(box, 34)
    user_entry.pack(anchor="w", ipady=6, pady=(4, 12))
    make_label(box, "Password (4+ characters)", 10, True).pack(anchor="w")
    pass_entry = make_entry(box, 34, show="*")
    pass_entry.pack(anchor="w", ipady=6, pady=(4, 12))
    make_label(box, "Confirm password", 10, True).pack(anchor="w")
    confirm_entry = make_entry(box, 34, show="*")
    confirm_entry.pack(anchor="w", ipady=6, pady=(4, 18))

    def do_signup():
        username = user_entry.get().strip()
        password = pass_entry.get()
        if len(username) < 3:
            messagebox.showerror("Sign up", "Username must be at least 3 characters.")
            return
        if len(password) < 4:
            messagebox.showerror("Sign up", "Password must be at least 4 characters.")
            return
        if password != confirm_entry.get():
            messagebox.showerror("Sign up", "Passwords do not match.")
            return
        if sign_up(username, password):
            messagebox.showinfo("Sign up", "Account created. Please log in.")
            show_login()
        else:
            messagebox.showerror("Sign up", "That username is already taken.")

    confirm_entry.bind("<Return>", lambda e: do_signup())
    make_button(box, "Create account", do_signup).pack(fill="x", ipady=3)
    user_entry.focus_set()


def show_dashboard():
    clear()
    state.update({"redraw": show_dashboard, "form_getter": None, "editing_id": None})
    t = theme()
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    header("My Resumes", f"{greeting}, {state['username']}. Let's build something great.")

    rows = get_my_resumes(state["user_id"])
    state["list_rows"] = rows

    stats = tk.Frame(container, bg=t["bg"])
    stats.pack(fill="x", padx=22, pady=(16, 4))
    avg = round(sum(completeness(r) for r in rows) / len(rows)) if rows else 0
    latest = (rows[0]["name"] or "Untitled") if rows else "None yet"
    stat_card(stats, "Total resumes", str(len(rows)), t["accent"])
    stat_card(stats, "Average completeness", f"{avg}%", t["accent2"])
    stat_card(stats, "Latest resume", latest[:20], t["good"])

    bar = tk.Frame(container, bg=t["bg"])
    bar.pack(fill="x", padx=28, pady=(12, 4))
    search_var = tk.StringVar()
    make_entry(bar, 38, textvariable=search_var).pack(side="left", ipady=7)
    make_button(bar, "+ New Resume", lambda: show_editor(None)).pack(side="right")

    inner = scroll_area()

    def render():
        for w in inner.winfo_children():
            w.destroy()
        if not rows:
            make_label(inner, "No resumes yet. Click '+ New Resume' to start your first one.",
                       11, muted=True).pack(pady=40)
            return
        q = search_var.get().strip().lower()
        shown = [r for r in rows if q in (r["name"] or "").lower() or q in (r["template"] or "").lower()]
        if not shown:
            make_label(inner, "No resumes match your search.", 11, muted=True).pack(pady=40)
            return
        for r in shown:
            resume_card(inner, r)

    search_var.trace_add("write", lambda *a: render())
    render()


def show_editor(resume=None):
    clear()
    state["editor_resume"] = resume
    state["redraw"] = lambda: show_editor(state["editor_resume"])
    state["editing_id"] = resume["id"] if resume else None
    source = state.pop("draft", None) or resume or {}

    def val(key):
        return source.get(key) or ""

    state["color"] = val("color") or "#4f46e5"
    state["photo"] = val("photo_path")
    t = theme()

    title = f"Editing: {resume['name'] or 'Untitled'}" if resume else "New Resume"
    header(title, "Fill the tabs on the left. The preview on the right updates as you type.",
           back=show_dashboard)

    actions = tk.Frame(container, bg=t["bg"])
    actions.pack(side="bottom", fill="x", padx=28, pady=(0, 18))
    body = tk.Frame(container, bg=t["bg"])
    body.pack(fill="both", expand=True, padx=28, pady=12)
    body.columnconfigure(0, weight=3)
    body.columnconfigure(1, weight=2)
    body.rowconfigure(0, weight=1)

    left = card(body)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
    right = card(body)
    right.grid(row=0, column=1, sticky="nsew", padx=(9, 0))

    nb = ttk.Notebook(left)
    nb.pack(fill="both", expand=True, padx=12, pady=12)

    widgets = {}
    template_var = tk.StringVar(value=val("template") or "Classic")

    def get_form_data():
        data = {}
        for key, w in widgets.items():
            if isinstance(w, tk.Entry):
                data[key] = w.get().strip()
            else:
                data[key] = w.get("1.0", "end-1c").strip()
        data["template"] = template_var.get()
        data["color"] = state["color"]
        data["photo_path"] = state["photo"]
        return data

    state["form_getter"] = get_form_data

    def tab(title):
        page = tk.Frame(nb, bg=t["card"], padx=20, pady=18)
        nb.add(page, text=title)
        return page

    def field(parent, label, key, height=None, hint=None):
        make_label(parent, label, 10, True).pack(anchor="w", pady=(8, 0))
        if hint:
            make_label(parent, hint, 9, muted=True).pack(anchor="w")
        if height:
            w = make_text(parent, height)
            w.pack(fill="both", expand=True, pady=(4, 0))
            w.insert("1.0", val(key))
        else:
            w = make_entry(parent, 50)
            w.pack(anchor="w", ipady=6, pady=(4, 0))
            w.insert(0, val(key))
        widgets[key] = w
        return w

    personal = tab("Personal")
    field(personal, "Full name *", "name")
    field(personal, "Phone * (10 or more digits)", "phone")
    field(personal, "Email *", "email")
    field(personal, "Professional summary", "summary", height=6, hint="2 to 3 lines about who you are")

    education = tab("Education")
    field(education, "Education", "education", height=12, hint="One per line: Degree - College - Year")

    skills_tab = tab("Skills")
    field(skills_tab, "Skills", "skills", height=6, hint="Comma separated, e.g. Python, SQL, Tkinter, Teamwork")

    experience_tab = tab("Experience")
    field(experience_tab, "Experience", "experience", height=12,
          hint="One per line: Role - Company - Duration - What you did")

    projects_tab = tab("Projects")
    field(projects_tab, "Projects", "projects", height=12, hint="One per line: Project title - What it does")

    design = tab("Design")
    make_label(design, "Template", 10, True).pack(anchor="w", pady=(8, 2))
    combo = ttk.Combobox(design, textvariable=template_var, values=["Classic", "Modern", "Minimal"],
                         state="readonly", width=30, font=("Segoe UI", 11))
    combo.pack(anchor="w", ipady=4)
    desc = make_label(design, TEMPLATE_INFO.get(template_var.get(), ""), 9, muted=True)
    desc.pack(anchor="w", pady=(4, 0))

    def on_template(e=None):
        desc.config(text=TEMPLATE_INFO.get(template_var.get(), ""))
        refresh_preview()

    combo.bind("<<ComboboxSelected>>", on_template)

    make_label(design, "Accent color", 10, True).pack(anchor="w", pady=(18, 2))
    color_row = tk.Frame(design, bg=t["card"])
    color_row.pack(anchor="w")
    swatch = tk.Label(color_row, width=6, bg=state["color"], relief="flat")
    swatch.pack(side="left", padx=(0, 12), ipady=6)

    def pick_color():
        result = colorchooser.askcolor(color=state["color"], title="Choose accent color")
        if result and result[1]:
            state["color"] = result[1]
            swatch.config(bg=result[1])
            refresh_preview()

    make_button(color_row, "Choose color", pick_color, "ghost").pack(side="left")

    make_label(design, "Profile photo (optional)", 10, True).pack(anchor="w", pady=(18, 2))
    thumb = tk.Label(design, bg=t["card"], fg=t["muted"], text="No photo selected")
    thumb.pack(anchor="w", pady=(0, 8))
    photo_row = tk.Frame(design, bg=t["card"])
    photo_row.pack(anchor="w")

    def show_thumb():
        path = state["photo"]
        if path and os.path.exists(path):
            img = Image.open(path)
            img.thumbnail((120, 120))
            state["thumb"] = ImageTk.PhotoImage(img)
            thumb.config(image=state["thumb"], text="")
        else:
            state["thumb"] = None
            thumb.config(image="", text="No photo selected")

    def pick_photo():
        path = filedialog.askopenfilename(title="Choose photo", filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if not path:
            return
        try:
            with Image.open(path) as img:
                img.verify()
        except Exception:
            messagebox.showerror("Photo error", "That file is not a valid image.")
            return
        state["photo"] = path
        show_thumb()
        refresh_preview()

    def remove_photo():
        state["photo"] = ""
        show_thumb()
        refresh_preview()

    make_button(photo_row, "Upload photo", pick_photo, "ghost").pack(side="left", padx=(0, 8))
    make_button(photo_row, "Remove", remove_photo, "ghost").pack(side="left")
    show_thumb()

    ats = tab("ATS Check")
    make_label(ats, "Paste a job description. Green words are in your resume. Red words are missing.",
               9, muted=True).pack(anchor="w")
    job = make_text(ats, 9)
    job.pack(fill="both", expand=True, pady=(6, 8))
    job.insert("1.0", val("job_description"))
    widgets["job_description"] = job
    job.tag_configure("hit", background="#bbf7d0", foreground="#14532d")
    job.tag_configure("miss", background="#fecaca", foreground="#7f1d1d")

    def check_ats():
        raw = job.get("1.0", "end-1c")
        if not raw.strip():
            messagebox.showwarning("ATS Check", "Paste a job description first.")
            return
        resume_text = build_preview_text(get_form_data())
        resume_lower = resume_text.lower()
        job.tag_remove("hit", "1.0", "end")
        job.tag_remove("miss", "1.0", "end")
        keywords = set()
        for m in re.finditer(r"[a-zA-Z+#]+", raw):
            w = m.group().lower()
            if len(w) <= 2 or w in STOPWORDS:
                continue
            keywords.add(w)
            tag = "hit" if w in resume_lower else "miss"
            job.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        score, missing = ats_score(resume_text, raw)
        color = t["good"] if score >= 70 else t["warn"] if score >= 40 else t["bad"]
        score_label.config(text=f"{score}%", fg=color)
        ats_bar["value"] = score
        matched_label.config(text=f"Matched {len(keywords) - len(missing)} of {len(keywords)} keywords")
        missing_label.config(text=("Missing: " + ", ".join(missing[:30])) if missing
                             else "Great match. Every keyword is in your resume.")

    make_button(ats, "Check match", check_ats).pack(anchor="w", pady=(0, 8))
    result = tk.Frame(ats, bg=t["card"])
    result.pack(fill="x")
    score_label = tk.Label(result, text="0%", bg=t["card"], fg=t["muted"], font=("Segoe UI", 22, "bold"))
    score_label.pack(anchor="w")
    ats_bar = ttk.Progressbar(result, maximum=100, style="Accent.Horizontal.TProgressbar")
    ats_bar.pack(fill="x", pady=(2, 6))
    matched_label = make_label(result, "Run the check to see your match score.", 9, muted=True)
    matched_label.pack(anchor="w")
    missing_label = make_label(result, "", 9, wrap=470)
    missing_label.pack(anchor="w", pady=(4, 8))

    head = tk.Frame(right, bg=t["card"])
    head.pack(fill="x", padx=18, pady=(16, 6))
    make_label(head, "Live preview", 13, True).pack(side="left")
    pct_label = tk.Label(head, text="0% complete", bg=t["card"], fg=t["muted"], font=("Segoe UI", 10, "bold"))
    pct_label.pack(side="right")
    prog = ttk.Progressbar(right, maximum=100, style="Accent.Horizontal.TProgressbar")
    prog.pack(fill="x", padx=18, pady=(0, 10))
    skills_row = tk.Frame(right, bg=t["card"])
    skills_row.pack(fill="x", padx=18, pady=(0, 10))
    preview = tk.Text(right, wrap="word", bg=t["entry"], fg=t["fg"], relief="flat", bd=0,
                      highlightthickness=0, padx=18, pady=12, font=("Segoe UI", 10), state="disabled")
    preview.pack(fill="both", expand=True, padx=18, pady=(0, 18))
    preview.tag_configure("name", font=("Segoe UI", 19, "bold"), foreground=state["color"], spacing3=2)
    preview.tag_configure("contact", font=("Segoe UI", 9), foreground=t["muted"], spacing3=8)
    preview.tag_configure("head", font=("Segoe UI", 11, "bold"), foreground=state["color"], spacing1=10, spacing3=3)
    preview.tag_configure("body", font=("Segoe UI", 10), spacing3=2)
    preview.tag_configure("bullet", font=("Segoe UI", 10), lmargin1=14, lmargin2=26, spacing3=2)

    def render_chips(text):
        for w in skills_row.winfo_children():
            w.destroy()
        items = [s.strip() for s in text.split(",") if s.strip()][:12]
        for i, item in enumerate(items):
            chip = tk.Label(skills_row, text=item, bg=state["color"], fg="#ffffff",
                            font=("Segoe UI", 9, "bold"), padx=9, pady=3)
            chip.grid(row=i // 4, column=i % 4, padx=3, pady=3, sticky="w")

    def refresh_preview():
        data = get_form_data()
        pct = completeness(data)
        prog["value"] = pct
        pct_color = t["bad"] if pct < 50 else t["warn"] if pct < 100 else t["good"]
        pct_label.config(text=f"{pct}% complete", fg=pct_color)
        render_chips(data["skills"])
        preview.config(state="normal")
        preview.delete("1.0", "end")
        preview.tag_configure("name", foreground=state["color"])
        preview.tag_configure("head", foreground=state["color"])
        preview.insert("end", (data["name"] or "Your Name") + "\n", "name")
        contact = " | ".join(x for x in [data["email"], data["phone"]] if x)
        if contact:
            preview.insert("end", contact + "\n", "contact")
        for title_text, key in SECTIONS:
            text = data.get(key, "")
            if not text:
                continue
            preview.insert("end", title_text.upper() + "\n", "head")
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if key in BULLET_KEYS:
                    preview.insert("end", "• " + line + "\n", "bullet")
                else:
                    preview.insert("end", line + "\n", "body")
        preview.config(state="disabled")

    for w in widgets.values():
        w.bind("<KeyRelease>", lambda e: refresh_preview())

    def save_clicked():
        data = get_form_data()
        error = validate(data)
        if error:
            messagebox.showerror("Check your input", error)
            return
        if state["editing_id"]:
            update_resume(state["editing_id"], state["user_id"], data)
        else:
            state["editing_id"] = save_resume(state["user_id"], data)
        state["editor_resume"] = get_resume(state["editing_id"], state["user_id"])
        toast("Resume saved", "good")

    def safe_name(data):
        return re.sub(r"[^A-Za-z0-9_]+", "_", data["name"]).strip("_") or "resume"

    def export_pdf_clicked():
        data = get_form_data()
        error = validate(data)
        if error:
            messagebox.showerror("Check your input", error)
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"{safe_name(data)}_resume.pdf",
                                            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            export_pdf(data, path)
            messagebox.showinfo("PDF created", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("PDF error", str(e))

    def export_txt_clicked():
        data = get_form_data()
        error = validate(data)
        if error:
            messagebox.showerror("Check your input", error)
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=f"{safe_name(data)}_resume.txt",
                                            filetypes=[("Text", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_preview_text(data))
        toast("Text file exported", "accent")

    state["save_fn"] = save_clicked
    make_button(actions, "Save resume  (Ctrl+S)", save_clicked).pack(side="left")
    make_button(actions, "Export PDF", export_pdf_clicked, "ghost").pack(side="left", padx=10)
    make_button(actions, "Export TXT", export_txt_clicked, "ghost").pack(side="left")
    make_label(actions, "Tip: Ctrl+S saves anytime", 9, muted=True).pack(side="right")

    refresh_preview()


root.bind("<Control-s>", lambda e: state["save_fn"]() if state["save_fn"] else None)

create_tables()
show_login()
root.mainloop()
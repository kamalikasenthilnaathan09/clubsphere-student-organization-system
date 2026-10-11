# AI Copilot routes extracted from app.py (uses copilot_service.py)
# -------------------------------------------------------------------------
# AI CLUB COPILOT / USER AI ASSISTANT ROUTES
# -------------------------------------------------------------------------

PERMITTED_COPILOT_ROLES = ('Treasurer', 'Event Organizer', 'Volunteer', 'Member')


@app.route('/copilot', methods=['GET'])
@login_required
def copilot_chat():
    user_role = session.get('role')
    if user_role not in PERMITTED_COPILOT_ROLES:
        flash('Access denied. The AI Assistant is available on student and member portals.', 'warning')
        return redirect(url_for('dashboard'))

    prompt = request.args.get('prompt', '').strip()
    initial_response = None
    if prompt:
        db = get_db()
        current_user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'full_name': session.get('full_name'),
            'role': session.get('role')
        }
        initial_response = copilot_service.ask_copilot(db, current_user, prompt)
        if initial_response.get('status') == 'ok' and initial_response.get('response'):
            session['copilot_history'] = [
                {'role': 'user', 'content': prompt},
                {'role': 'assistant', 'content': initial_response['response']}
            ]
            session.modified = True
    else:
        # Clear previous transient history if visiting chat fresh without prompt
        session.setdefault('copilot_history', [])

    ai_config = copilot_service.get_ai_config()
    return render_template(
        'copilot.html',
        ai_config=ai_config,
        initial_prompt=prompt,
        initial_response=initial_response
    )


@app.route('/copilot/ask', methods=['POST'])
@login_required
def copilot_ask():
    user_role = session.get('role')
    if user_role not in PERMITTED_COPILOT_ROLES:
        return jsonify({
            'status': 'error',
            'message': 'Access denied. The AI Assistant is available for member and student accounts.'
        }), 403

    data = request.get_json(silent=True) or request.form
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'status': 'error', 'message': 'Message is required.'}), 400

    raw_history = data.get('history')
    if not isinstance(raw_history, list):
        raw_history = session.get('copilot_history', [])

    clean_history = []
    for turn in raw_history[-8:]:
        if isinstance(turn, dict) and 'role' in turn and 'content' in turn:
            role = 'user' if turn.get('role') == 'user' else 'assistant'
            content = str(turn.get('content', '')).strip()
            if content:
                clean_history.append({'role': role, 'content': content[:2500]})

    db = get_db()
    current_user = {
        'id': session.get('user_id'),
        'username': session.get('username'),
        'full_name': session.get('full_name'),
        'role': session.get('role')
    }
    result = copilot_service.ask_copilot(db, current_user, message, history=clean_history)

    # Persist turns in user session
    hist = session.get('copilot_history', [])
    hist.append({'role': 'user', 'content': message})
    if result.get('status') == 'ok' and result.get('response'):
        hist.append({'role': 'assistant', 'content': result['response']})
    session['copilot_history'] = hist[-16:]
    session.modified = True

    return jsonify(result), 200


@app.route('/copilot/clear', methods=['POST'])
@login_required
def copilot_clear():
    user_role = session.get('role')
    if user_role not in PERMITTED_COPILOT_ROLES:
        return jsonify({'status': 'error', 'message': 'Access denied.'}), 403

    session.pop('copilot_history', None)

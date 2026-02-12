from web_socket.manager import manager

async def session_success_notification(user_id: str, role: str, session_id: str):
    try:
        payload = {
            "type": "NOTIFICATION",
            "title": "✅ Interview Session Created!",
            "message": f"Your {role} interview session has been created successfully.",
            "sessionId": session_id
        }
        await manager.send_to_user(user_id, payload)
    except Exception as e:
        print(f"⚠️ Failed to send success notification: {e}")

async def quiz_start_success_notification(user_id: str, session_id: str, number_of_questions: int):
    try:
        payload = {
            "type": "NOTIFICATION",
            "title": "📝 Quiz Started!",
            "message": f"Your quiz with {number_of_questions} questions has started. You have {number_of_questions * 3} minutes to complete it.",
            "sessionId": session_id,
            "quizType": "started"
        }
        await manager.send_to_user(user_id, payload)
        print(f"📨 Quiz start notification sent to user {user_id}")
    except Exception as e:
        print(f"⚠️ Failed to send quiz start notification: {e}")

async def quiz_submitted_notification(user_id: str, session_id: str, score: int, total: int, percentage: float, submission_type: str):
    """Send general quiz submission notification for both manual and auto submit"""
    try:
        payload = {
            "type": "NOTIFICATION",
            "title": "📊 Quiz Submitted!",
            "message": f"Your quiz has been submitted. You scored {score}/{total} ({percentage:.1f}%).",
            "sessionId": session_id,
            "quizType": "submitted",
            "score": score,
            "total": total,
            "percentage": percentage,
            "submissionType": submission_type
        }
        await manager.send_to_user(user_id, payload)
        print(f"📨 Quiz submission notification sent to user {user_id}")
    except Exception as e:
        print(f"⚠️ Failed to send quiz submission notification: {e}")

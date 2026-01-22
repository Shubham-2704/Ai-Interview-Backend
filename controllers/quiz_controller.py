from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime, timedelta
from config.database import database
from utils.helper import *
from models.quiz_model import *
from controllers.ai_controller import generate_with_gemini, parse_gemini_json_response
from utils.prompt import generate_quiz_prompt, evaluate_quiz_prompt
import json

users = database["users"]
sessions = database["sessions"]
questions = database["questions"]
quizzes = database["quizzes"]

async def generate_quiz_service(session_id: str, number_of_questions: int, user):
    # 1. Get session and its questions
    session = await sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        raise HTTPException(404, "Session not found")
    
    # 2. Fetch session questions for context
    session_questions = await questions.find(
        {"session": ObjectId(session_id)}
    ).to_list(length=20)
    
    if not session_questions:
        raise HTTPException(400, "No questions found in session to generate quiz")
    
    # 3. Prepare context from session questions
    questions_context = []
    for q in session_questions[:10]:  # Use first 10 as context
        questions_context.append({
            "question": q.get("question", ""),
            "answer": q.get("answer", "")
        })
    
    # 4. Generate quiz using AI
    try:
        prompt = generate_quiz_prompt(
            questions_context=json.dumps(questions_context, ensure_ascii=False),
            number_of_questions=number_of_questions,
            experience_level=session.get("experience", 2)
        )
        
        ai_response = await generate_with_gemini(prompt, user_id=user["id"])
        
        # Parse AI response using your existing parser
        quiz_questions = parse_gemini_json_response(ai_response)
        
        if not isinstance(quiz_questions, list):
            raise ValueError("AI did not return a valid list of questions")
        
        # 5. Validate each question has required fields
        for i, q in enumerate(quiz_questions):
            if not all(key in q for key in ["question", "options", "correctAnswer", "explanation"]):
                raise ValueError(f"Question {i+1} missing required fields")
            if len(q.get("options", [])) != 4:
                raise ValueError(f"Question {i+1} must have exactly 4 options")
            if not 0 <= q.get("correctAnswer", -1) <= 3:
                raise ValueError(f"Question {i+1} has invalid correctAnswer index")
        
        # 6. Create quiz document
        quiz_doc = {
            "sessionId": ObjectId(session_id),
            "userId": ObjectId(user["id"]),
            "questions": quiz_questions,
            "totalQuestions": number_of_questions,
            "sessionInfo": {
                "role": session.get("role"),
                "experience": session.get("experience"),
                "topics": session.get("topicsToFocus")
            },
            "createdAt": datetime.now(),
            "status": "active",  # active, completed, expired
            "score": None,
            "submittedAt": None,
            "timeSpent": None
        }
        
        result = await quizzes.insert_one(quiz_doc)
        quiz_id = str(result.inserted_id)
        
        # Return quiz data (without answers for security)
        quiz_data = []
        for q in quiz_questions:
            quiz_data.append({
                "question": q["question"],
                "options": q["options"]
                # Don't include correctAnswer or explanation yet
            })
        
        return {
            "success": True,
            "quizId": quiz_id,
            "questions": quiz_data,
            "totalQuestions": number_of_questions,
            "sessionInfo": quiz_doc["sessionInfo"],
            "createdAt": quiz_doc["createdAt"].isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating quiz: {e}")
        raise HTTPException(500, f"Failed to generate quiz: {str(e)}")

async def submit_quiz_service(quiz_id: str, answers: List[int], time_spent: int, user):
    # 1. Get quiz
    quiz = await quizzes.find_one({"_id": ObjectId(quiz_id)})
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    
    if quiz.get("userId") != ObjectId(user["id"]):
        raise HTTPException(403, "Not authorized")
    
    if quiz.get("status") == "completed":
        raise HTTPException(400, "Quiz already submitted")
    
    # 2. Validate answers length
    if len(answers) != quiz.get("totalQuestions"):
        raise HTTPException(400, f"Invalid number of answers. Expected {quiz.get('totalQuestions')}, got {len(answers)}")
    
    # 3. Validate answer indices
    for i, answer in enumerate(answers):
        if answer is None:
            raise HTTPException(400, f"Question {i+1} not answered")
        if not 0 <= answer <= 3:
            raise HTTPException(400, f"Invalid answer index for question {i+1}")
    
    # 4. Evaluate with AI
    try:
        prompt = evaluate_quiz_prompt(
            questions=quiz["questions"],
            answers=answers
        )
        
        ai_response = await generate_with_gemini(prompt, user_id=user["id"])
        result_data = parse_gemini_json_response(ai_response)
        
        # 5. Calculate score manually as backup
        correct_count = 0
        for i, q in enumerate(quiz["questions"]):
            if i < len(answers) and answers[i] == q.get("correctAnswer"):
                correct_count += 1
        
        # Use AI evaluation or fallback to manual calculation
        if "score" not in result_data:
            result_data["score"] = correct_count
            result_data["total"] = len(quiz["questions"])
            result_data["percentage"] = (correct_count / len(quiz["questions"])) * 100
        
         # Create results with options from original questions
        results_with_options = []
        ai_questions = result_data.get("questions", [])
        
        for i, original_q in enumerate(quiz["questions"]):
            result_item = {
                "question": original_q.get("question", ""),
                "options": original_q.get("options", []),  # CRITICAL: Keep options
                "userAnswer": answers[i] if i < len(answers) else None,
                "correctAnswer": original_q.get("correctAnswer"),
                "isCorrect": answers[i] == original_q.get("correctAnswer") if i < len(answers) else False,
                "explanation": ""
            }
            
            # Add explanation from AI if available
            if i < len(ai_questions) and "explanation" in ai_questions[i]:
                result_item["explanation"] = ai_questions[i]["explanation"]
            
            results_with_options.append(result_item)
        
        # 6. Update quiz
        update_data = {
            "status": "completed",
            "userAnswers": answers,
            "score": result_data["score"],
            "totalQuestions": result_data.get("total", len(quiz["questions"])),
            "percentage": result_data.get("percentage", 0),
            "results": results_with_options,  # CHANGE THIS LINE: Use results_with_options
            "feedback": result_data.get("feedback", ""),
            "timeSpent": time_spent,
            "submittedAt": datetime.now(),
            "completedAt": datetime.now()
        }
        
        await quizzes.update_one(
            {"_id": ObjectId(quiz_id)},
            {"$set": update_data}
        )
        
        # 7. Return results
        return {
            "success": True,
            "quizId": quiz_id,
            "score": update_data["score"],
            "total": update_data["totalQuestions"],
            "percentage": update_data["percentage"],
            "questions": results_with_options, 
            "feedback": update_data["feedback"],
            "timeSpent": time_spent,
            "completedAt": update_data["completedAt"].isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error evaluating quiz: {e}")
        raise HTTPException(500, f"Failed to evaluate quiz: {str(e)}")

async def get_quiz_results_service(quiz_id: str, user):
    quiz = await quizzes.find_one({"_id": ObjectId(quiz_id)})
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    
    if quiz.get("userId") != ObjectId(user["id"]):
        raise HTTPException(403, "Not authorized")
    
    return serialize_doc(quiz)

async def get_user_quizzes_service(session_id: str, user):
    quizzes_list = await quizzes.find({
        "sessionId": ObjectId(session_id),
        "userId": ObjectId(user["id"])
    }).sort("createdAt", -1).to_list(length=20)
    
    return [serialize_doc(q) for q in quizzes_list]

async def delete_quiz_service(quiz_id: str, user):
    quiz = await quizzes.find_one({"_id": ObjectId(quiz_id)})
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    
    if quiz.get("userId") != ObjectId(user["id"]):
        raise HTTPException(403, "Not authorized")
    
    await quizzes.delete_one({"_id": ObjectId(quiz_id)})
    
    return {"success": True, "message": "Quiz deleted successfully"}

async def get_quiz_analytics_service(session_id: str, time_range: str, user):
    """
    Get analytics for all quizzes in a session
    """
    # 1. Get all quizzes for this session
    quizzes_list = await quizzes.find({
        "sessionId": ObjectId(session_id),
        "userId": ObjectId(user["id"]),
        "status": "completed"
    }).sort("createdAt", -1).to_list(None)
    
    if not quizzes_list:
        raise HTTPException(404, "No completed quizzes found for analytics")
    
    # 2. Calculate date range filter
    now = datetime.now()
    if time_range == "week":
        start_date = now - timedelta(days=7)
    elif time_range == "month":
        start_date = now - timedelta(days=30)
    else:  # "all"
        start_date = datetime.min
    
    # 3. Filter quizzes by date range
    filtered_quizzes = []
    for quiz in quizzes_list:
        quiz_date = quiz.get("createdAt")
        if quiz_date and quiz_date >= start_date:
            filtered_quizzes.append(quiz)
    
    if not filtered_quizzes:
        raise HTTPException(404, f"No quizzes found in the {time_range} time range")
    
    # 4. Calculate basic analytics
    total_quizzes = len(filtered_quizzes)
    total_questions = sum(q.get("totalQuestions", 0) for q in filtered_quizzes)
    total_correct = sum(q.get("score", 0) for q in filtered_quizzes)
    total_time_spent = sum(q.get("timeSpent", 0) for q in filtered_quizzes)
    
    average_score = (total_correct / total_questions * 100) if total_questions > 0 else 0
    best_score = max((q.get("percentage", 0) for q in filtered_quizzes), default=0)
    
    # 5. Calculate score distribution
    score_distribution = [0, 0, 0, 0, 0]  # 0: <60, 1: 60-69, 2: 70-79, 3: 80-89, 4: 90-100
    for quiz in filtered_quizzes:
        percentage = quiz.get("percentage", 0)
        if percentage >= 90:
            score_distribution[4] += 1
        elif percentage >= 80:
            score_distribution[3] += 1
        elif percentage >= 70:
            score_distribution[2] += 1
        elif percentage >= 60:
            score_distribution[1] += 1
        else:
            score_distribution[0] += 1
    
    # 6. Calculate daily performance (last 30 days max)
    daily_performance = {}
    for quiz in filtered_quizzes:
        quiz_date = quiz.get("createdAt")
        if quiz_date:
            date_str = quiz_date.strftime("%Y-%m-%d")
            if date_str not in daily_performance:
                daily_performance[date_str] = []
            daily_performance[date_str].append(quiz.get("percentage", 0))
    
    # Average daily scores
    daily_performance_list = []
    for date_str, scores in list(daily_performance.items())[-30:]:  # Last 30 days max
        avg_score = sum(scores) / len(scores) if scores else 0
        daily_performance_list.append({
            "date": date_str,
            "score": round(avg_score, 1)
        })
    
    # 7. Calculate improvement rate (compare first and last quiz)
    if len(filtered_quizzes) >= 2:
        first_quiz = filtered_quizzes[-1]  # Oldest
        last_quiz = filtered_quizzes[0]    # Most recent
        improvement_rate = last_quiz.get("percentage", 0) - first_quiz.get("percentage", 0)
    else:
        improvement_rate = 0
    
    # 8. Calculate completion rate
    total_attempts = await quizzes.count_documents({
        "sessionId": ObjectId(session_id),
        "userId": ObjectId(user["id"])
    })
    completion_rate = (total_quizzes / total_attempts * 100) if total_attempts > 0 else 100
    
    # 9. Return analytics data
    return {
        "success": True,
        "timeRange": time_range,
        "totalQuizzes": total_quizzes,
        "totalQuestions": total_questions,
        "totalTimeSpent": total_time_spent,
        "averageScore": round(average_score, 1),
        "bestScore": round(best_score, 1),
        "improvementRate": round(improvement_rate, 1),
        "completionRate": round(completion_rate, 1),
        "scoreDistribution": score_distribution,
        "dailyPerformance": daily_performance_list,
        "recentQuizzes": [
            {
                "id": str(q["_id"]),
                "date": q.get("createdAt").isoformat() if q.get("createdAt") else None,
                "score": q.get("score", 0),
                "total": q.get("totalQuestions", 0),
                "percentage": q.get("percentage", 0),
                "timeSpent": q.get("timeSpent", 0)
            }
            for q in filtered_quizzes[:5]  # Last 5 quizzes
        ]
    }

async def get_topic_performance_service(session_id: str, user):
    """
    Get topic-wise performance based on quiz results
    """
    # Get session info first
    session = await sessions.find_one({"_id": ObjectId(session_id)})
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Get all completed quizzes
    quizzes_list = await quizzes.find({
        "sessionId": ObjectId(session_id),
        "userId": ObjectId(user["id"]),
        "status": "completed"
    }).to_list(None)
    
    if not quizzes_list:
        # Return default topics from session
        topics = session.get("topicsToFocus", "").split(",") if session.get("topicsToFocus") else ["General"]
        return {
            "topicPerformance": [
                {"topic": topic.strip(), "score": 0}
                for topic in topics[:5]
            ]
        }
    
    # This is a simplified version - in reality, you'd need to analyze
    # which questions relate to which topics. For now, return mock data
    # based on session topics
    
    topics = session.get("topicsToFocus", "")
    if topics:
        topic_list = [t.strip() for t in topics.split(",")][:5]
    else:
        topic_list = ["Algorithms", "Data Structures", "System Design", "JavaScript", "React"]
    
    # Generate mock performance data (in real app, analyze quiz questions)
    topic_performance = []
    for i, topic in enumerate(topic_list):
        # Random score between 60-95 for demo
        score = 60 + (i * 5) + (hash(topic) % 20)
        if score > 95:
            score = 95
        topic_performance.append({
            "topic": topic,
            "score": score
        })
    
    return {
        "topicPerformance": topic_performance
    }

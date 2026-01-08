import re
import html
import markdown
import asyncio
import tempfile
import os
import base64
from typing import List, Dict
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


# UNIVERSAL CODE HIGHLIGHTING FOR ANY LANGUAGE
def _markdown_to_html(markdown_text: str) -> str:
    """Convert markdown to HTML with full syntax highlighting"""
    if not markdown_text:
        return ""

    # ---------- CODE BLOCKS ----------
    code_pattern = r'```(\w*)\n([\s\S]*?)```'

    def replace_code_block(match):
        language = match.group(1).lower() if match.group(1) else 'text'
        # CRITICAL: DO NOT escape HTML here
        code = match.group(2)  # Remove html.escape()
        
        # Apply highlighting
        highlighted_code = _universal_highlight_code(code, language)
        
        return f"""
<div class="code-container">
    <div class="code-header">
        <span class="language-badge">{language.upper() if language != 'text' else 'CODE'}</span>
    </div>
    <pre class="code-block"><code>{highlighted_code}</code></pre>
</div>
"""

    markdown_text = re.sub(code_pattern, replace_code_block, markdown_text, flags=re.DOTALL)

    # ---------- INLINE CODE ----------
    markdown_text = re.sub(
        r'`([^`]+)`',
        r'<span class="inline-code">\1</span>',
        markdown_text
    )

    # ---------- MARKDOWN CONVERSION ----------
    return markdown.markdown(
        markdown_text,
        extensions=['extra', 'sane_lists']
    )


def _universal_highlight_code(code: str, language: str) -> str:
    """Full syntax highlighting without nested HTML tags"""
    
    colors = {
        'keyword': '#D73A49',    # Soft red
        'string': '#032F62',     # Dark blue
        'number': '#005CC5',     # Blue
        'comment': '#6A737D',    # Gray
        'function': '#6F42C1',   # Purple
        'operator': '#24292E',   # Dark gray
    }
    
    # Step 1: Highlight multi-line comments FIRST (they span multiple lines)
    highlighted = re.sub(
        r'(/\*[\s\S]*?\*/|<!--[\s\S]*?-->)',
        f'<span style="color: {colors["comment"]}; font-style: italic">\\1</span>',
        code
    )
    
    # Step 2: Process line by line
    lines = highlighted.split('\n')
    processed_lines = []
    
    for line in lines:
        # Skip if already has comment highlighting from multi-line
        if 'style="color:' in line and 'italic' in line:
            processed_lines.append(line)
            continue
            
        original_line = line
        
        # Step 3: Highlight strings with SIMPLE pattern (avoid HTML conflicts)
        # Double quotes - simple pattern
        line = re.sub(
            r'"([^"\n]*)"',
            f'<span style="color: {colors["string"]}">"\\1"</span>',
            line
        )
        
        # Single quotes - simple pattern
        line = re.sub(
            r"'([^'\n]*)'",
            f'<span style="color: {colors["string"]}">\'\\1\'</span>',
            line
        )
        
        # Step 4: Highlight numbers
        line = re.sub(
            r'\b(\d+\.?\d*)\b',
            f'<span style="color: {colors["number"]}">\\1</span>',
            line
        )
        
        # Hex numbers
        line = re.sub(
            r'\b(0x[0-9a-fA-F]+)\b',
            f'<span style="color: {colors["number"]}">\\1</span>',
            line
        )
        
        # Step 5: Highlight single-line comments (only if not already in string)
        # Check if line has // but not inside quotes
        if '//' in original_line and '"' not in original_line[:original_line.find('//')]:
            line = re.sub(
                r'(//.*)$',
                f'<span style="color: {colors["comment"]}; font-style: italic">\\1</span>',
                line
            )
        
        # Step 6: Highlight operators
        operators = [
            ('\\+\\+', '++'),
            ('--', '--'),
            ('<=', '<='),
            ('>=', '>='),
            ('==', '=='),
            ('!=', '!='),
            ('&&', '&&'),
            ('\\|\\|', '||'),
            ('<<', '<<'),
            ('>>', '>>'),
            ('\\+=', '+='),
            ('-=', '-='),
            ('\\*=', '*='),
            ('/=', '/='),
            ('%=', '%='),
        ]
        
        for op_pattern, op_text in operators:
            line = re.sub(
                f'({re.escape(op_pattern)})',
                f'<span style="color: {colors["operator"]}">\\1</span>',
                line
            )
        
        # Step 7: Highlight language-specific keywords
        if language in ['javascript', 'js', 'typescript', 'ts']:
            keywords = ['function', 'const', 'let', 'var', 'if', 'else', 'return', 
                       'for', 'while', 'do', 'switch', 'case', 'break', 'continue',
                       'try', 'catch', 'finally', 'throw', 'new', 'delete', 'typeof',
                       'instanceof', 'in', 'of', 'export', 'import', 'default', 'class',
                       'extends', 'super', 'this', 'null', 'true', 'false', 'undefined',
                       'async', 'await', 'yield', 'static', 'get', 'set']
            
            for keyword in keywords:
                line = re.sub(
                    f'\\b({keyword})\\b',
                    f'<span style="color: {colors["keyword"]}">\\1</span>',
                    line
                )
        
        elif language in ['python', 'py']:
            keywords = ['def', 'class', 'if', 'elif', 'else', 'for', 'while', 'try',
                       'except', 'finally', 'with', 'as', 'import', 'from', 'return',
                       'yield', 'async', 'await', 'lambda', 'True', 'False', 'None',
                       'and', 'or', 'not', 'is', 'in', 'global', 'nonlocal']
            
            for keyword in keywords:
                line = re.sub(
                    f'\\b({keyword})\\b',
                    f'<span style="color: {colors["keyword"]}">\\1</span>',
                    line
                )
        
        # Step 8: Highlight function calls
        # Match functionName( pattern
        line = re.sub(
            r'\b([a-zA-Z_][a-zA-Z0-9_]*)\(',
            f'<span style="color: {colors["function"]}">\\1</span>(',
            line
        )
        
        processed_lines.append(line)
    
    highlighted = '\n'.join(processed_lines)
    
    return highlighted

# PDF GENERATOR
async def generate_pdf(session: Dict, questions: List[Dict], output_path: str):
    """Generate PDF using Selenium/Chromium"""
    html_content = _generate_html(session, questions)
    
    return await asyncio.to_thread(_generate_pdf_with_selenium, html_content, output_path)


def _generate_pdf_with_selenium(html_content: str, output_path: str):
    """Synchronous function to generate PDF using Selenium"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # A4 paper size
    print_options = {
        'landscape': False,
        'displayHeaderFooter': False,
        'printBackground': True,
        'preferCSSPageSize': True,
        'paperWidth': 8.27,
        'paperHeight': 11.69,
        'marginTop': 0.5,
        'marginBottom': 0.5,
        'marginLeft': 0.5,
        'marginRight': 0.5,
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        temp_html = f.name
        f.write(html_content)
    
    driver = None
    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(f"file://{temp_html}")
        driver.implicitly_wait(2)
        
        result = driver.execute_cdp_cmd('Page.printToPDF', print_options)
        pdf_data = base64.b64decode(result['data'])
        
        with open(output_path, 'wb') as pdf_file:
            pdf_file.write(pdf_data)
            
    finally:
        if driver:
            driver.quit()
        os.unlink(temp_html)

# HTML GENERATION WITH ALTERNATING QUESTION COLORS
def _generate_html(session: Dict, questions: List[Dict]) -> str:
    """Generate HTML with alternating question background colors"""
    
    # Build questions with alternating colors
    questions_html = []
    color_classes = ['question-color-2', 'question-color-2', 'question-color-2']
    
    for idx, q in enumerate(questions, start=1):
        question = html.escape(str(q.get("question", "")))
        answer = q.get("answer", "")
        
        # Cycle through 3 colors (1, 2, 3, 1, 2, 3, ...)
        color_class = color_classes[(idx - 1) % 3]
        
        questions_html.append(f"""
        <div class="question-container {color_class}">
            <div class="question-header">
                <div class="question-number">Q{idx}</div>
            </div>
            <h2 class="question-title">{question}</h2>
            <div class="answer-content">
                {_markdown_to_html(answer)}
            </div>
        </div>
        """)
    
    questions_content = "\n".join(questions_html)
    
    # Format session info
    role = html.escape(str(session.get("role", "")))
    experience = html.escape(str(session.get("experience", "")))
    current_date = datetime.now().strftime("%B %d, %Y")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Interview Prep - {role}</title>
        <style>
            /* A4 Page Setup - NO automatic page breaks */
            @page {{
                size: A4;
                margin: 0.5in;
            }}
            
            /* Base Styles */
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
                    body {{
                font-family: 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background: #FFFFFF;
                font-size: 12px;
                min-height: 100vh;            
                display: flex;                
                flex-direction: column;       
                justify-content: center;      
                align-items: center;          
                padding: 20px;
            }}
            
            /* Add this container after body styles */
            .container {{
                max-width: 800px;
                width: 100%;
                margin: 0 auto;
            }}
            
            /* Header */
            .header {{
                text-align: center;
                margin-bottom: 30px;
                padding-bottom: 15px;
                border-bottom: 2px solid #4A90E2;
            }}
            
            .title {{
                color: #2C3E50;
                font-size: 22px;
                font-weight: bold;
                margin-bottom: 8px;
            }}
            
            .subtitle {{
                color: #7F8C8D;
                font-size: 14px;
                margin-bottom: 15px;
            }}
            
            /* Session Info */
                    /* Session Info */
            .session-info {{
                background: #F8F9FA;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 25px;
                border-left: 4px solid #4A90E2;
                text-align: center;          
            }}
            
            .info-grid {{                     
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 10px;
                justify-items: center;
            }}
            
            .info-item {{                     
                display: flex;
                flex-direction: column;
                margin-bottom: 8px;
            }}
            
            .info-label {{
                font-weight: bold;
                color: #2C3E50;
                font-size: 12px;            
                margin-bottom: 2px;         
            }}
            
            .info-value {{
                color: #34495E;
                font-size: 14px;            
            }}
            
            /* Question Containers with ALTERNATING COLORS */
            .question-container {{
                margin-bottom: 25px;
                border-radius: 8px;
                padding: 20px;
                page-break-inside: avoid; 
            }}
            
            /* Three alternating background colors */
            .question-color-1 {{
                background: #FFFFFF;
                border: 1px solid #E0E0E0;
            }}
            
            .question-color-2 {{
                background: #F8F9FA;
                border: 1px solid #DFE6E9;
            }}
            
            .question-color-3 {{
                background: #F1F8FF;
                border: 1px solid #D6E4FF;
            }}
            
            .question-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 1px solid rgba(0,0,0,0.1);
            }}
            
            .question-number {{
                background: #4A90E2;
                color: white;
                padding: 5px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }}
            
            .question-title {{
                color: #2C3E50;
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 15px;
                line-height: 1.4;
            }}
            
            /* Answer Content */
            .answer-content {{
                color: #444;
                font-size: 12px;
                line-height: 1.6;
            }}
            
            .answer-content p {{
                margin-bottom: 12px;
            }}
            
            .answer-content h1, h2, h3 {{
                color: #2C3E50;
                margin-top: 18px;
                margin-bottom: 12px;
            }}
            
            .answer-content ul, ol {{
                margin-left: 20px;
                margin-bottom: 15px;
            }}
            
            .answer-content li {{
                margin-bottom: 6px;
            }}
            
            /* Code Blocks */
            .code-container {{
                margin: 15px 0;
                border-radius: 6px;
                overflow: hidden;
                background: #F6F8FA;
                border: 1px solid #E1E4E8;
            }}
            
            .code-header {{
                background: #EFF2F6;
                color: #586069;
                padding: 6px 12px;
                font-family: 'SF Mono', Monaco, Consolas, monospace;
                font-size: 11px;
                border-bottom: 1px solid #E1E4E8;
            }}
            
            .language-badge {{
                background: #4A90E2;
                color: white;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
            }}
            
            .code-block {{
                background: #F6F8FA;
                color: #24292E;
                padding: 15px;
                margin: 0;
                overflow-x: auto;
                font-family: 'SF Mono', Monaco, Consolas, monospace;
                font-size: 11px;
                line-height: 1.5;
                tab-size: 4;
            }}
            
            .code-block code {{
                display: block;
                white-space: pre-wrap;
            }}
            
            /* Inline Code */
            .inline-code {{
                background: #EFF2F6;
                color: #D73A49;
                padding: 2px 5px;
                border-radius: 3px;
                font-family: 'SF Mono', Monaco, Consolas, monospace;
                font-size: 11px;
                border: 1px solid #E1E4E8;
            }}
            
            /* Tables */
            .answer-content table {{
                width: 100%;
                border-collapse: collapse;
                margin: 12px 0;
                font-size: 11px;
            }}
            
            .answer-content th {{
                background: #F8F9FA;
                color: #2C3E50;
                font-weight: bold;
                padding: 8px 10px;
                border: 1px solid #E0E0E0;
            }}
            
            .answer-content td {{
                padding: 8px 10px;
                border: 1px solid #E0E0E0;
            }}
            
            /* Footer */
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #E0E0E0;
                color: #95A5A6;
                font-size: 11px;
            }}
            
            /* Print Styles - NO automatic page breaks */
            @media print {{
                body {{
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                    padding: 0;
                    margin: 0;
                }}
                
                .question-container {{
                    break-inside: avoid;
                    margin-bottom: 20px;
                }}
            }}
        </style>
    </head>
    <body>
            <div class="container">                     
            <div class="header">
                <h1 class="title">Interview Preparation</h1>
                <p class="subtitle">Technical Questions & Answers</p>
            </div>
            
            <div class="session-info">
                <div class="info-grid">             
                    <div class="info-item">         
                        <span class="info-label">Role:</span>
                        <span class="info-value">{role}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Experience:</span>
                        <span class="info-value">{experience} years</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Total Questions:</span>
                        <span class="info-value">{len(questions)}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Generated Date:</span>
                        <span class="info-value">{current_date}</span>
                    </div>
                </div>
            </div>
        
        {questions_content}
        
        <div class="footer">
                <p>Generated on {current_date} • Interview Preparation Assistant</p>
            </div>
        </div>                                    
    </body>
    </html>
    """
    
    return html_content

import os, re

d = '/Users/shashank/Downloads/sample2/sample/xplbs/templates/indent/print/'
files = [f for f in os.listdir(d) if f.endswith('_print.html')]

overlay = """
<style>
.loading-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.95); z-index: 10000; align-items: center; justify-content: center; flex-direction: column; font-family: sans-serif; }
.loading-spinner { border: 6px solid #f3f3f3; border-top: 6px solid #002060; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; margin-bottom: 20px; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
</style>
<div id="loadingOverlay" class="loading-overlay">
    <div class="loading-spinner"></div>
    <h2 style="color: #002060; margin: 0;">Attaching Document...</h2>
    <p style="color: #666; margin-top: 10px;">Please wait while the document is being processed.</p>
</div>
</body>
"""

for fname in files:
    path = os.path.join(d, fname)
    with open(path, 'r') as f:
        content = f.read()
        
    def repl(m):
        msg = m.group(1)
        return f'onclick="if(confirm(\'{msg}\')) {{ document.getElementById(\'loadingOverlay\').style.display = \'flex\'; document.getElementById(\'attachForm\').submit(); }}"'
    
    content = re.sub(r'onclick="if\(confirm\(\'([^\']+)\'\)\)\s*document\.getElementById\(\'attachForm\'\)\.submit\(\);"', repl, content)
    
    if "loading-overlay" not in content:
        content = content.replace('</body>', overlay)
    
    with open(path, 'w') as f:
        f.write(content)

print('Done attaching overlay to print templates')

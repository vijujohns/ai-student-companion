from pathlib import Path
text = Path("v3/backend/app/api/routes.py").read_text()
s = '@router.get("/context")\ndef get_learning_context'
start = text.find(s)
print('start', start)
end = text.find(s, start+1)
print('second', end)
print('first snippet:', repr(text[start:start+200]))
print('---')
print('end snippet:', repr(text[end-200:end]))

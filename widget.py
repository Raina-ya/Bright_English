"""Floating daily English companion. Run after server.py has created learning_data.json."""
import tkinter as tk, json, webbrowser
from pathlib import Path
ROOT=Path(__file__).parent; DATA=ROOT/'learning_data.json'
PROVERBS=[('Actions speak louder than words.','行動勝於言語。'),('Every cloud has a silver lining.','黑暗中總有一線光明。'),('Practice makes perfect.','熟能生巧。'),('Where there is a will, there is a way.','有志者事竟成。'),('The early bird catches the worm.','早起的鳥兒有蟲吃。'),('A journey of a thousand miles begins with a single step.','千里之行，始於足下。'),('Better late than never.','遲做總比不做好。')]
def data():
 try:return json.loads(DATA.read_text(encoding='utf8'))
 except:return {}
root=tk.Tk(); root.overrideredirect(True); root.attributes('-topmost',True); root.configure(bg='#243b6b')
today=__import__('datetime').date.today(); en,zh=PROVERBS[today.toordinal()%len(PROVERBS)]
frame=tk.Frame(root,bg='#fff8e9',padx=15,pady=12); frame.pack(padx=2,pady=2)
tk.Label(frame,text='☀️  Bright English',font=('Segoe UI',12,'bold'),bg='#fff8e9',fg='#e9774e').pack(anchor='w')
tk.Label(frame,text=en,wraplength=265,justify='left',font=('Segoe UI',10,'bold'),bg='#fff8e9',fg='#243b6b').pack(anchor='w',pady=(7,0))
tk.Label(frame,text=zh,wraplength=265,justify='left',font=('Microsoft JhengHei',9),bg='#fff8e9',fg='#6f7890').pack(anchor='w')
words=', '.join(data().get('days',{}).get(str(today),{}).get('words',[])[:6]) or '打開學習站開始今天的新詞吧！'
tk.Label(frame,text='今日新詞：'+words,wraplength=265,justify='left',font=('Microsoft JhengHei',9),bg='#fff8e9',fg='#257a72').pack(anchor='w',pady=8)
row=tk.Frame(frame,bg='#fff8e9'); row.pack(fill='x')
tk.Button(row,text='打開學習站',command=lambda:webbrowser.open('http://localhost:8765'),bg='#65c6b4',fg='white',relief='flat').pack(side='left')
tk.Button(row,text='×',command=root.destroy,bg='#fff8e9',fg='#6f7890',relief='flat').pack(side='right')
drag={'x':0,'y':0}; frame.bind('<Button-1>',lambda e:drag.update(x=e.x,y=e.y)); frame.bind('<B1-Motion>',lambda e:root.geometry(f'+{e.x_root-drag["x"]}+{e.y_root-drag["y"]}'))
root.geometry('+80+120'); root.mainloop()

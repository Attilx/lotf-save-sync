from pathlib import Path
import os, sys, queue, threading, traceback, subprocess, zipfile
import tkinter as tk
from tkinter import ttk, filedialog
from .engine import Options
from .workflow import Source, prepare, create_output
from .errors import SyncError, FormatError
from .i18n import TEXT

BASE=Path(__file__).resolve().parent.parent
FONT = 'Segoe UI' if os.name=='nt' else 'Helvetica'
BG='#0b1422';CARD='#142235';FG='#ecf2fb';MUTED='#a7b8cf';ACCENT='#59dbc4'

class Application:
    def __init__(self, root):
        self.root=root;self.lang='it';self.busy=False;self.prepared=None;self.result=None
        self.sources={};self.events=queue.Queue();self.status_key='ready';self.status_args={}
        root.title('LOTF Save Sync · 1.0.1 beta');root.geometry(f'1100x{min(920,root.winfo_screenheight()-80)}');root.minsize(920,660);root.configure(bg=BG)
        root.option_add('*Font',(FONT,10));root.protocol('WM_DELETE_WINDOW',self.close)
        self.paths={k:tk.StringVar() for k in ('host','guest')}
        self.slots={k:tk.StringVar() for k in ('host','guest')}
        self.options={k:tk.BooleanVar(value=True) for k in Options.__dataclass_fields__}
        self.include=tk.BooleanVar(value=True)
        default=Path.home()/'Documents'
        self.destination=tk.StringVar(value=str(default if default.is_dir() else Path.home()))
        self.language=tk.StringVar(value='Italiano')
        self.style=ttk.Style(root);self.style.theme_use('clam')
        self.style.configure('.',background=BG,foreground=FG,fieldbackground=CARD,bordercolor='#30415a',lightcolor=CARD,darkcolor=CARD,font=(FONT,10))
        self.style.configure('TFrame',background=BG)
        self.style.configure('Card.TFrame',background=CARD)
        self.style.configure('TLabel',background=BG,foreground=FG)
        self.style.configure('Muted.TLabel',foreground=MUTED)
        self.style.configure('Card.TLabel',background=CARD)
        self.style.configure('Heading.TLabel',font=(FONT,10,'bold'),foreground=ACCENT)
        self.style.configure('TButton',padding=(12,7),background='#263a53',foreground=FG,borderwidth=0)
        self.style.map('TButton',background=[('active','#365573'),('disabled','#1d2b3e')],foreground=[('disabled','#71839a')])
        self.style.configure('Primary.TButton',background=ACCENT,foreground=BG,font=(FONT,10,'bold'))
        self.style.map('Primary.TButton',background=[('active','#89efdc'),('disabled','#233b44')],foreground=[('disabled','#71839a')])
        self.style.configure('TCheckbutton',background=BG,foreground=FG,padding=(0,2))
        self.style.map('TCheckbutton',background=[('active',BG)],foreground=[('disabled','#71839a')])
        self.style.configure('Treeview',background=CARD,fieldbackground=CARD,rowheight=24,borderwidth=0)
        self.style.configure('Treeview.Heading',background='#21334b',font=(FONT,10,'bold'),padding=4)
        self.style.configure('TEntry',padding=6)
        self.style.configure('TCombobox',padding=4,arrowsize=15)
        self.style.map('TCombobox',fieldbackground=[('readonly',CARD)],foreground=[('readonly',FG)])
        self.style.configure('Horizontal.TProgressbar',background=ACCENT,troughcolor=CARD,borderwidth=0)
        self.build();root.after(80,self.poll)

    def tr(self,key,**kwargs):
        return TEXT[self.lang].get(key,key).format(**kwargs)

    def build(self):
        if hasattr(self,'viewport'):
            self.viewport.destroy()
        self.viewport=ttk.Frame(self.root);self.viewport.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(self.viewport,bg=BG,highlightthickness=0)
        outer_scroll=ttk.Scrollbar(self.viewport,orient='vertical',command=self.canvas.yview)
        outer_scroll.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.configure(yscrollcommand=outer_scroll.set)
        self.shell=ttk.Frame(self.canvas,padding=(24,18))
        self.content_id=self.canvas.create_window((0,0),window=self.shell,anchor='nw')
        self.wrap_labels=[]
        frame=self.shell;frame.columnconfigure(0,weight=1);frame.rowconfigure(4,weight=1)
        top=ttk.Frame(frame);top.grid(row=0,column=0,sticky='ew',pady=(0,12));top.columnconfigure(0,weight=1)
        ttk.Label(top,text='LOTF Save Sync',font=(FONT,24,'bold')).grid(row=0,column=0,sticky='w')
        ttk.Label(top,text=self.tr('subtitle'),style='Muted.TLabel').grid(row=1,column=0,sticky='w',pady=(3,0))
        self.langbox=ttk.Combobox(top,textvariable=self.language,values=['Italiano','English'],state='readonly',width=11)
        self.langbox.grid(row=0,column=1,padx=10);self.langbox.bind('<<ComboboxSelected>>',self.switch_language)
        ttk.Button(top,text=self.tr('help'),command=self.help).grid(row=0,column=2)
        sources=ttk.Frame(frame);sources.grid(row=1,column=0,sticky='ew');sources.columnconfigure((0,1),weight=1,uniform='sources')
        self.source_controls=[];self.slotboxes={}
        for col,key in enumerate(('host','guest')):
            card=ttk.Frame(sources,style='Card.TFrame',padding=14);card.grid(row=0,column=col,sticky='nsew',padx=(0,6) if col==0 else (6,0));card.columnconfigure(0,weight=1)
            ttk.Label(card,text=self.tr(key),style='Card.TLabel',font=(FONT,10,'bold')).grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,8))
            entry=ttk.Entry(card,textvariable=self.paths[key],state='readonly');entry.grid(row=1,column=0,columnspan=3,sticky='ew')
            ttk.Label(card,text=self.tr('source_hint'),style='Card.TLabel',foreground=MUTED,font=(FONT,9)).grid(row=2,column=0,columnspan=3,sticky='w',pady=(5,8))
            box=ttk.Combobox(card,textvariable=self.slots[key],values=self.sources[key].slots if key in self.sources else (),state='readonly',width=20)
            box.grid(row=3,column=0,sticky='ew',padx=(0,7));box.bind('<<ComboboxSelected>>',lambda e:self.invalidate());self.slotboxes[key]=box
            for i,(label,folder) in enumerate((('file',False),('folder',True))):
                btn=ttk.Button(card,text=self.tr(label),command=lambda k=key,f=folder:self.choose(k,f));btn.grid(row=3,column=i+1,padx=(3,0));self.source_controls.append(btn)
        section=ttk.Frame(frame);section.grid(row=2,column=0,sticky='ew',pady=(14,6));section.columnconfigure((0,1),weight=1,uniform='opts')
        ttk.Label(section,text=self.tr('select'),style='Heading.TLabel').grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,7))
        self.option_widgets=[]
        for idx,key in enumerate(self.options):
            area=ttk.Frame(section);area.grid(row=1+idx//2,column=idx%2,sticky='nw',padx=(0,12),pady=(0,6))
            cb=ttk.Checkbutton(area,text=self.tr(key),variable=self.options[key],command=self.invalidate)
            cb.pack(anchor='w');self.option_widgets.append(cb)
            desc=ttk.Label(area,text=self.tr(key+'_desc'),style='Muted.TLabel',font=(FONT,9),wraplength=470)
            desc.pack(anchor='w',padx=(23,0));self.wrap_labels.append(desc)
        self.selection_note=ttk.Label(section,text='',style='Muted.TLabel',font=(FONT,9),wraplength=1020)
        self.selection_note.grid(row=3,column=0,columnspan=2,sticky='w',pady=(1,3))
        self.protect_label=ttk.Label(frame,text=self.tr('protect'),foreground=ACCENT,font=(FONT,10),wraplength=1000)
        self.protect_label.grid(row=3,column=0,sticky='w',pady=(0,8))
        comp=ttk.Frame(frame);comp.grid(row=4,column=0,sticky='nsew');comp.columnconfigure(0,weight=1);comp.rowconfigure(1,weight=1)
        ttk.Label(comp,text=self.tr('comparison'),style='Heading.TLabel').grid(row=0,column=0,sticky='w',pady=(0,6))
        self.table=ttk.Treeview(comp,columns=('field','host','guest'),show='headings',height=5,selectmode='none')
        for key,title,width in [('field','field',205),('host','host_col',370),('guest','guest_col',370)]:
            self.table.heading(key,text=self.tr(title));self.table.column(key,width=width,minwidth=120,stretch=True)
        self.table.grid(row=1,column=0,sticky='nsew')
        sb=ttk.Scrollbar(comp,orient='vertical',command=self.table.yview);sb.grid(row=1,column=1,sticky='ns');self.table.configure(yscrollcommand=sb.set)
        self.backupbox=ttk.Checkbutton(comp,text=self.tr('backups'),variable=self.include,command=self.invalidate)
        self.backupbox.grid(row=2,column=0,sticky='w',pady=(7,0))
        output=ttk.Frame(frame);output.grid(row=5,column=0,sticky='ew',pady=(10,8));output.columnconfigure(0,weight=1)
        ttk.Label(output,text=self.tr('output'),style='Heading.TLabel').grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,5))
        self.outentry=ttk.Entry(output,textvariable=self.destination);self.outentry.grid(row=1,column=0,sticky='ew')
        self.outbrowse=ttk.Button(output,text=self.tr('browse'),command=self.choose_destination);self.outbrowse.grid(row=1,column=1,padx=(8,0))
        self.status_label=ttk.Label(frame,text='',style='Muted.TLabel',wraplength=1020)
        self.status_label.grid(row=6,column=0,sticky='w',pady=(2,6))
        self.progress=ttk.Progressbar(frame,mode='indeterminate');self.progress.grid(row=7,column=0,sticky='ew',pady=(0,9))
        actions=ttk.Frame(frame);actions.grid(row=8,column=0,sticky='ew');actions.columnconfigure(1,weight=1)
        self.analyze_button=ttk.Button(actions,text=self.tr('analyze'),command=self.analyze)
        self.analyze_button.grid(row=0,column=0,sticky='w')
        self.open_button=ttk.Button(actions,text=self.tr('open'),command=self.open_result)
        self.open_button.grid(row=0,column=1,sticky='e',padx=8)
        self.create_button=ttk.Button(actions,text=self.tr('create'),command=self.create,style='Primary.TButton')
        self.create_button.grid(row=0,column=2,sticky='e')
        self.update_note();self.set_status(self.status_key,**self.status_args);self.controls()
        if self.prepared:self.fill_comparison()
        self.canvas.bind('<Configure>',self.resize)
        self.shell.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.root.bind('<MouseWheel>',self.wheel)

    def resize(self,event):
        for label in self.wrap_labels:label.configure(wraplength=max(260,(event.width-48)//2-42))
        for label in (self.selection_note,self.protect_label,self.status_label):label.configure(wraplength=max(500,event.width-60))
        self.canvas.itemconfigure(self.content_id,width=event.width,height=max(event.height,self.shell.winfo_reqheight()))
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def wheel(self,event):
        if event.widget.winfo_toplevel() is self.root and not isinstance(event.widget,(ttk.Treeview,tk.Text)):
            self.canvas.yview_scroll(-int(event.delta/120),'units')

    def switch_language(self,event=None):
        self.lang='en' if self.language.get()=='English' else 'it';self.build()

    def set_status(self,key,**kwargs):
        self.status_key=key;self.status_args=kwargs
        self.status_label.configure(text=self.tr(key,**kwargs))

    def update_note(self):
        self.selection_note.configure(text=self.tr('full' if all(v.get() for v in self.options.values()) else 'partial')+'\n'+self.tr('risk'))

    def controls(self):
        for w in self.source_controls+self.option_widgets+[self.backupbox,self.outbrowse,self.outentry,self.analyze_button]:
            w.configure(state='disabled' if self.busy else 'normal')
        for w in list(self.slotboxes.values())+[self.langbox]:w.configure(state='disabled' if self.busy else 'readonly')
        self.create_button.configure(state='normal' if self.prepared and not self.busy else 'disabled')
        self.open_button.configure(state='normal' if self.result and not self.busy else 'disabled')

    def invalidate(self):
        self.prepared=None;self.table.delete(*self.table.get_children());self.set_status('changed');self.update_note();self.controls()

    def load_source(self,key,path):
        source=Source.discover(path);self.sources[key]=source;self.paths[key].set(str(source.path))
        self.slotboxes[key].configure(values=source.slots)
        self.slots[key].set(source.slots[0] if len(source.slots)==1 else '')
        self.invalidate()

    def choose(self,key,folder=False):
        path=filedialog.askdirectory(parent=self.root,title=self.tr('choose_folder')) if folder else filedialog.askopenfilename(parent=self.root,title=self.tr('choose_file'),filetypes=[(self.tr('savefiles'),'*.sav *.zip'),(self.tr('allfiles'),'*.*')])
        if path:
            try:self.load_source(key,path)
            except Exception as exc:self.show_error(exc)

    def choose_destination(self):
        path=filedialog.askdirectory(parent=self.root,title=self.tr('output'),initialdir=self.destination.get())
        if path:self.destination.set(path)

    def start_job(self,fn,kind):
        self.busy=True;self.controls();self.progress.start(12)
        def work():
            try:self.events.put(('success',kind,fn()))
            except Exception as exc:self.events.put(('error',exc,traceback.format_exc()))
        threading.Thread(target=work,daemon=True).start()

    def analyze(self):
        if not all(k in self.sources and self.slots[k].get() in self.sources[k].slots for k in ('host','guest')):
            self.show_error(SyncError('choose_sources'));return
        self.prepared=None;self.table.delete(*self.table.get_children());self.set_status('busy')
        args=(self.sources['host'],self.slots['host'].get(),self.sources['guest'],self.slots['guest'].get(),Options(**{k:v.get() for k,v in self.options.items()}),self.include.get())
        self.start_job(lambda:prepare(*args,progress=lambda s:self.events.put(('progress',s,None))),'analyze')

    def create(self):
        if not self.prepared:return
        prepared=self.prepared;destination=self.destination.get();self.set_status('writing')
        self.start_job(lambda:create_output(prepared,destination,BASE/'docs'),'create')

    def poll(self):
        try:
            while True:
                event,a,b=self.events.get_nowait()
                if event=='progress':
                    if a.startswith('checking:'):self.status_label.configure(text=self.tr('checking')+' '+a.split(':',1)[1]+'…')
                    else:self.set_status(a)
                else:
                    self.busy=False;self.progress.stop();self.progress.configure(value=0)
                    if event=='error':
                        self.prepared=None;self.set_status('error');self.show_error(a,b)
                    elif a=='analyze':
                        self.prepared=b;self.fill_comparison();self.set_status('preview_ok',n=len(b.outputs))
                    elif a=='create':
                        self.result=b;self.set_status('done',path=str(b));self.prepared=None
                    self.controls()
        except queue.Empty:pass
        self.root.after(80,self.poll)

    def fill_comparison(self):
        p=self.prepared;h,g=p.host.info,p.guest.info
        self.table.delete(*self.table.get_children())
        for key in ('player','version','ng','difficulty','mods_count','anchors_count','checkpoint','files_count'):
            if key=='mods_count':
                a=len(h['modifiers']);b=str(len(g['modifiers']))+' ('+self.tr('same' if h['modifiers']==g['modifiers'] and set(h['modifier_tags'])==set(g['modifier_tags']) else 'different')+')'
            elif key=='anchors_count':a,b=sum(bool(v) for v in h['anchors'].values()),sum(bool(v) for v in g['anchors'].values())
            elif key=='files_count':a,b='-',len(p.outputs)
            else:a,b=h[key],g[key]
            if key=='difficulty':a,b=[self.tr('legacy') if v=='Legacy (default)' else v for v in (a,b)]
            self.table.insert('', 'end',values=(self.tr(key),a,b))

    def show_error(self,exc,detail=None):
        if isinstance(exc,SyncError):message=self.tr(exc.code,detail=exc.detail)
        elif isinstance(exc,(FormatError,ValueError,KeyError,IndexError,zipfile.BadZipFile)):message=self.tr('invalid_format')
        elif isinstance(exc,OSError):message=self.tr('io_error')
        else:message=self.tr('unexpected_error')
        window=tk.Toplevel(self.root);window.title(self.tr('error'));window.configure(bg=BG);window.geometry('720x380');window.transient(self.root)
        ttk.Label(window,text=message,wraplength=665,padding=20).pack(fill='x')
        ttk.Label(window,text=self.tr('error_detail'),style='Muted.TLabel',padding=(20,0)).pack(anchor='w')
        box=tk.Text(window,bg=CARD,fg=FG,height=9,wrap='word',font=('Consolas',9),relief='flat')
        box.pack(fill='both',expand=True,padx=20,pady=10);box.insert('1.0',detail or f'{type(exc).__name__}: {exc}');box.configure(state='disabled')
        ttk.Button(window,text=self.tr('close'),command=window.destroy).pack(anchor='e',padx=20,pady=(0,15));window.grab_set()

    def help(self):
        window=tk.Toplevel(self.root);window.title(self.tr('help')+' · LOTF Save Sync');window.geometry('830x650');window.configure(bg=BG)
        frame=ttk.Frame(window,padding=18);frame.pack(fill='both',expand=True)
        box=tk.Text(frame,bg=CARD,fg=FG,wrap='word',font=(FONT,11),padx=18,pady=16,relief='flat')
        scroll=ttk.Scrollbar(frame,command=box.yview);scroll.pack(side='right',fill='y');box.configure(yscrollcommand=scroll.set);box.pack(fill='both',expand=True)
        try:content=(BASE/'docs'/f'GUIDE_{self.lang.upper()}.txt').read_text(encoding='utf-8')
        except OSError:content=self.tr('io_error')
        box.insert('1.0',content);box.configure(state='disabled')

    def open_result(self):
        if self.result:
            if os.name=='nt':os.startfile(str(self.result))
            else:subprocess.Popen(['open' if sys.platform=='darwin' else 'xdg-open',str(self.result)])

    def close(self):
        if self.busy:return
        self.root.destroy()


def main():
    root=tk.Tk();Application(root);root.mainloop()

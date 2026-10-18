"""Console startup diagnostics for the Windows portable distribution."""
from pathlib import Path
import os,sys,traceback
BASE=Path(__file__).resolve().parent
print('LOTF Save Sync — diagnostica / diagnostics')
print('Python:',sys.version)
print('Executable:',sys.executable)
print('Application:',BASE)
try:
    if os.name=='nt':
        _dll=os.add_dll_directory(str(BASE/'runtime/DLLs'))
        os.environ['TCL_LIBRARY']=str(BASE/'runtime/tcl/tcl8.6')
        os.environ['TK_LIBRARY']=str(BASE/'runtime/tcl/tk8.6')
    import tkinter as tk
    from lotfsync.engine import Options
    root=tk.Tk();root.withdraw()
    print('Tcl:',root.tk.call('info','patchlevel'))
    print('Tk:',root.tk.call('package','provide','Tk'))
    root.destroy()
    print('Avvio interfaccia / Starting interface...')
    from lotfsync.gui import main
    main()
except Exception:
    traceback.print_exc()
    print('\nInvia questo messaggio per diagnosticare il problema.\nShare this output to diagnose the issue.')
    sys.exit(1)

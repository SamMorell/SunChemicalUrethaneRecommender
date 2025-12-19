# Stable Streamlit Cloud entrypoint (keep URL unchanged)
from urethane.apps.urethane_streamlit_1_0_2 import main

if __name__ == "__main__":
    main()
else:
    # Streamlit executes the script as a module; ensure app runs in that case too.
    main()

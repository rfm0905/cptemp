# Overengineered Function to Copy Homework Templates 

I was bored and did way tm just cause I was too lazy to copy my homework templates manually, so this is a CLI utility that takes in your target directories and does it for you. There's already a `--help` option, and you can `fzf`   search too if you want. It has Nord theming too! The screenshots explain themselves. 

The default and tempdirs are hard-coded, if someone acc uses this make it use environment variables yourself. Note this will overwrite the exiting files / directory in the targets, but it also autocreates them if they don't exist. Defaults to cwd if no target is specified. Use `-a` if you want to copy contents direclty, without renaming to the target name.  

<img width="752" height="442" alt="Screenshot 2026-02-16 at 7 33 19 PM" src="https://github.com/user-attachments/assets/6f8de2ec-d503-45b0-92d7-ab927f6a7c54" />

<br/>
<br/>

<img width="762" height="392" alt="Screenshot 2026-02-16 at 7 33 41 PM" src="https://github.com/user-attachments/assets/a2c8534c-da1e-4baf-b6e5-f4aa8a875776" />


(fzf is really needed for my two templates here) 

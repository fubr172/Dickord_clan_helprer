Code Overview
Main Functionalities
User Role Management:
Automatically assigns the role "Гость сообщества" (Community Guest) to new members.
Issues warnings to users and manages roles accordingly.
Vacation Requests:
Users can request vacation by specifying a reason and an end date.
Admins can approve or decline these requests through interactive buttons.
Voice Channel Management:
Creates temporary voice channels when users connect to a designated channel.
Deletes empty voice channels while preserving specific channels like "Создать канал" (Create Channel) and "AFK".
Logging:
Logs events and errors to the console and can send logs to a specified Discord channel.
Command Handling:
Provides commands for vacation requests, warnings, and role management.
Constants and Their Meanings
AFK_CHANNEL_NAME: "AFK"
The name of the channel where users are moved when they are inactive.
CREATE_CHANNEL_NAME: "Создать канал"
The name of the channel where users can create new voice channels.
VOICE_CHANNELS_CATEGORY_NAME: "Голосовые каналы"
The category name under which voice channels are organized.
NEW_MEMBER_ROLE_NAME: "Гость сообщества"
The role assigned to new members joining the server.
WARNED_ROLE_NAME: "Предупрежден"
The role given to users when they receive a warning.
VACATION_ROLE_NAME: "Отпуск"
The role assigned to users who are on vacation.
ALLOWED_ROLES: []
A list of roles permitted to manage vacation requests and other administrative tasks.
CHECKED_ROLES: []
A list of roles that are monitored for certain actions or commands.
INSTRUCTOR_ROLE_NAME: []
Placeholder for roles designated for instructors or similar positions.
LLOWED_ROLES: []
This appears to be a typo and should likely be ALLOWED_ROLES or another relevant list.
last_message: None
A variable intended to store the last message sent by the bot or in a specific context.
Setting Up the Bot with a Virtual Environment
Step 1: Install Python
Ensure you have Python installed on your system. You can download it from the official Python website. Make sure to check the box to add Python to your PATH during installation.
Step 2: Create a Virtual Environment
Open your command line interface (CLI):
On Windows, use Command Prompt or PowerShell.
On macOS or Linux, use Terminal.
Navigate to your project directory:
Use the cd command to change to the directory where you want to create your bot:
bash
cd path/to/your/project/directory
Create a virtual environment:
Run the following command:
bash
python -m venv venv
Activate the virtual environment:
On Windows:
bash
venv\Scripts\activate
On macOS or Linux:
bash
source venv/bin/activate
Step 3: Install Required Libraries
With the virtual environment activated, install the necessary libraries using pip:
bash
pip install discord.py aiogram python-dotenv
Step 4: Set Up Your Bot
Create a new Python file (e.g., bot.py) in your project directory and copy the bot code into this file.
Configure Tokens and IDs:
Replace placeholders in the code with your actual Discord and Telegram bot tokens, as well as any channel or role IDs specific to your server.
Run Your Bot:
After setting everything up, run your bot with:
bash
python bot.py
Step 5: Managing Your Environment
When finished working on your project, deactivate the virtual environment by running:
bash
deactivate
You can also create a requirements.txt file by running:
bash
pip freeze > requirements.txt
This file lists all installed packages and their versions, making it easier to replicate the environment later or share it with others.
This setup allows you to effectively manage dependencies for your Discord bot while ensuring that it runs smoothly within its own isolated environment.

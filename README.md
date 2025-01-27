# Discord and Telegram Integration Bot

The provided code is a Discord bot integrated with Telegram, designed to manage user roles, vacation requests, and voice channels. Below is an overview of its functionalities, constants, and setup instructions using a virtual environment.

## Code Overview

### Main Functionalities

#### User Role Management
- Automatically assigns the role **"Гость сообщества" (Community Guest)** to new members.
- Issues warnings to users and manages roles accordingly.

#### Vacation Requests
- Users can request vacation by specifying a reason and an end date.
- Admins can approve or decline these requests through interactive buttons.

#### Voice Channel Management
- Creates temporary voice channels when users connect to a designated channel.
- Deletes empty voice channels, while preserving specific ones like **"Создать канал" (Create Channel)** and **"AFK"**.

#### Logging
- Logs events and errors to the console.
- Can send logs to a specified Discord channel.

#### Command Handling
- Provides commands for vacation requests, warnings, and role management.

---

### Constants and Their Meanings

- **AFK_CHANNEL_NAME:** `"AFK"`  
  The name of the channel where users are moved when they are inactive.
- **CREATE_CHANNEL_NAME:** `"Создать канал"`  
  The name of the channel where users can create new voice channels.
- **VOICE_CHANNELS_CATEGORY_NAME:** `"Голосовые каналы"`  
  The category name under which voice channels are organized.
- **NEW_MEMBER_ROLE_NAME:** `"Гость сообщества"`  
  The role assigned to new members joining the server.
- **WARNED_ROLE_NAME:** `"Предупрежден"`  
  The role given to users when they receive a warning.
- **VACATION_ROLE_NAME:** `"Отпуск"`  
  The role assigned to users who are on vacation.
- **ALLOWED_ROLES:** `[]`  
  A list of roles permitted to manage vacation requests and other administrative tasks.
- **CHECKED_ROLES:** `[]`  
  A list of roles that are monitored for certain actions or commands.
- **INSTRUCTOR_ROLE_NAME:** `[]`  
  Placeholder for roles designated for instructors or similar positions.
- **LLOWED_ROLES:** `[]`  
  Appears to be a typo and should likely be `ALLOWED_ROLES` or another relevant list.
- **last_message:** `None`  
  A variable intended to store the last message sent by the bot or in a specific context.

---

## Setting Up the Bot with a Virtual Environment

### Step 1: Install Python
1. Download Python from the [official Python website](https://www.python.org/).
2. Ensure you check the box to add Python to your PATH during installation.

---

### Step 2: Create a Virtual Environment
1. Open your command line interface (CLI):
   - On Windows: Use **Command Prompt** or **PowerShell**.
   - On macOS/Linux: Use **Terminal**.
2. Navigate to your project directory:
   ```bash
   cd path/to/your/project/directory

---
### Step 3: Install Required Libraries

Install the necessary libraries using `pip`:

```bash
pip install discord.py aiogram python-dotenv
```

---

## Step 4: Set Up Your Bot

1. Create a new Python file (e.g., `bot.py`) in your project directory and copy the bot code into this file.
2. Configure tokens and IDs:
   - Replace placeholders in the code with your actual **Discord** and **Telegram** bot tokens.
   - Include any channel or role IDs specific to your server.
3. Run your bot:
   ```bash
   python bot.py
   ```

   ---

## Step 5: Managing Your Environment

1. Deactivate the virtual environment when done:
   ```bash
   deactivate
   ```
2. Create a requirements.txt file for sharing or replicating the environment:
   ```
   pip freeze > requirements.txt
   ```

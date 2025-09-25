# Instagram Automation

Python scripts to automate Instagram login, fetch cookies, and compare follower/following lists.

## Prerequisites

- Python 3.10+
- Chrome browser (for Selenium)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Secrets are loaded from a `.env` file at the project root. Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Update `.env` with your Instagram account details:

```
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password
```

> Keep `.env` out of version control. Your actual credentials should never be committed.

## Usage

Run the main script after setting the environment variables:

```bash
python main.py
```

The script will log into Instagram, collect the follower/following data, and print the accounts that do not mutually follow.

# Heroku Deploy

**Important Notes**
1. This branch non-editable.
2. Generate all your private files from master branch (token.pickle, config.env, drive_folder, cookies.txt ...) since the generators not available in heroku branch but you should add the private files in heroku branch not master or use variables links in `config.env`.
3. You can only edit a2c.conf(aria2c) and qBittorrent.conf.
4. Don't add variables in heroku Environment, you can only add `CONFIG_FILE_URL`.
5. `BASE_URL_OF_BOT` variable is required to start the bot.
6. Incase any extra file added other than the private files or any edit in dockerfile or edit file not mentioned in note `3` your bot will not start.
7. Shell and Eval commands disabled in this branch.
8. `UPSTREAM_REPO` and `UPSTREAM_BRANCH` not working in this branch.
9. This branch uses megasdkrest and latest version of qBittorrent.

------

## Deploy With CLI

- Clone this repo:
```
git clone https://github.com/anasty17/mirror-leech-telegram-bot mirrorbot/ && cd mirrorbot
```
- Switch to heroku branch
  - **NOTE**: Don't commit changes in master branch. If you have committed your changes in master branch and after that you switched to heroku branch, the new added files(private files) will `NOT` appear in heroku branch.
```
git checkout heroku
```
- After adding your private files
```
git add . -f
```
- Commit your changes
```
git commit -m token
```
- Login to heroku
```
heroku login
```
- Create heroku app
```
heroku create --region us YOURAPPNAME
```
- Add remote
```
heroku git:remote -a YOURAPPNAME
```
- Create container
```
heroku stack:set container
```
- Push to heroku
```
git push heroku heroku:master -f
```

------

### Extras

- To create heroku-postgresql database
```
heroku addons:create heroku-postgresql
```
- To delete the app
```
heroku apps:destroy YOURAPPNAME
```
- To restart dyno
```
heroku restart
```
- To turn off dyno
```
heroku ps:scale web=0
```
- To turn on dyno
```
heroku ps:scale web=1
```
- To set heroku variable
```
heroku config:set VARNAME=VARTEXT
```
- To get live logs
```
heroku logs -t
```

------

## Deploy With Github Workflow

1. Go to Repository Settings -> Secrets

![Secrets](https://telegra.ph/file/9d6ed26f8981c2d2f226c.jpg)

2. Add the below Required Variables one by one by clicking New Repository Secret every time.

   - HEROKU_EMAIL: Heroku Account Email Id in which the above app will be deployed
   - HEROKU_API_KEY: Your Heroku API key, get it from https://dashboard.heroku.com/account
   - HEROKU_APP_NAME: Your Heroku app name, Name Must be unique
   - CONFIG_FILE_URL: Copy [This](https://raw.githubusercontent.com/anasty17/mirror-leech-telegram-bot/master/config_sample.env) in any text editor.Remove the _____REMOVE_THIS_LINE_____=True line and fill the variables. For details about config you can see Here. Go to https://gist.github.com and paste your config data. Rename the file to config.env then create secret gist. Click on Raw, copy the link. This will be your CONFIG_FILE_URL. Refer to below images for clarity.

![Steps from 1 to 3](https://telegra.ph/file/2a27cf34dc0bdba885de9.jpg)

![Step 4](https://telegra.ph/file/fb3b92a1d2c3c1b612ad0.jpg)

![Step 5](https://telegra.ph/file/f0b208e4ea980b575dbe2.jpg)

3. Remove commit id from raw link to be able to change variables without updating the CONFIG_FILE_URL in secrets. Should be in this form: https://gist.githubusercontent.com/username/gist-id/raw/config.env
   - Before: https://gist.githubusercontent.com/anasty17/8cce4a4b4e7f4ea47e948b2d058e52ac/raw/19ba5ab5eb43016422193319f28bc3c7dfb60f25/config.env
   - After: https://gist.githubusercontent.com/anasty17/8cce4a4b4e7f4ea47e948b2d058e52ac/raw/config.env

4. Add all your private files in this branch or use variables links in `config.env`.

5. After adding all the above Required Variables go to Github Actions tab in your repository.
   - Select Manually Deploy to Heroku workflow as shown below:

![Select Manual Deploy](https://telegra.ph/file/cff1c24de42c271b23239.jpg)

6. Choose `heroku` branch and click on Run workflow

![Run Workflow](https://telegra.ph/file/f44c7465d58f9f046328b.png)

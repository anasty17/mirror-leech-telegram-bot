#! /bin/bash

# Made with ❤ by @SpeedIndeed - Telegram

printf "This is an interactive script that will help you in deploying almost any mirrorbot. What do you want to do?
1) Deploying first time
2) Redeploying but already have credentials.json, token.pickle and SA folder (optional)
3) Check if appname is available 
4) Just commiting changes to existing repo\n"
while true; do
	read -p "Select one of the following: " choice
	case $choice in
            "1")
				echo -e "Firstly we will make credentials.json"
				echo -e "For that, follow the TUTORIAL 2 given in this post: https://telegra.ph/Deploying-your-own-Mirrorbot-10-19#TUTORIAL-2"
				echo -e "If this script closes in between then just re-run it. \n"
				for (( ; ; ))
				do
					read -p "After adding credentials.json, Press y : " cred
					if [ $cred = y -o $cred = Y ] ; then
						break
					else
						echo -e "Then do it first! \n"
					fi
				done
				
				echo -e "\nNow we will login to heroku"
				echo
				for (( ; ; ))
				do
					echo -e "Enter your Heroku credentials: \n"
					heroku login -i
					status=$?
					if test $status -eq 0; then
						echo -e "Signed in successfully \n"
					break
					fi
					echo -e "Invalid credentials, try again \n"
				done
				
				for (( ; ; ))
				do
					read -p "Enter unique appname for your bot: " bname
					heroku create $bname
					status=$?
					if test $status -eq 0; then
						echo -e "App created successfully \n"
					break
					fi
					echo -e "Appname is already taken, choose another one \n"
				done
				
				heroku git:remote -a $bname
				heroku stack:set container -a $bname
				pip3 install -r requirements-cli.txt
				pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
				echo -e "\nNow we will create token.pickle. Follow the instructions given. \n"
				sleep 5
				python -m pip install google-auth-oauthlib
				python3 generate_drive_token.py
				sleep 5
				echo -e "\nService Accounts (SA) help you bypass daily 750GB limit when you want to upload to Shared Drive/Team Drive (TD). Keeping this in mind, select one of the following: \n"
				echo -e "1) You don't have SA but want to use them? \n"
				echo -e "2) You already have SA and want to use them? \n"
				echo -e "3) You don't want to add SA \n"
				read -p "Enter your choice: " sa
				sleep 3
				if [ $sa = 1 ] ; then
					python -m pip install progress
					python3 gen_sa_accounts.py --list-projects
					echo -e "Choose the project id which contains credentails.json, that way you can avoid mess of multiple projects \n"
					echo
					read -p "Project id: " pid
					python3 gen_sa_accounts.py --enable-services $pid
					python3 gen_sa_accounts.py --create-sas $pid
					python3 gen_sa_accounts.py --download-keys $pid
					echo
				fi
				if [ $sa = 2 ] ; then
					python3 gen_sa_accounts.py --list-projects
					echo -e "Choose the project id which contains SA \n"
					echo
					read -p "Project id: " pid
					python3 gen_sa_accounts.py --download-keys $pid
					echo
				fi
				if [ $sa = 1 -o $sa = 2 ] ; then
					echo -e "As you can see, a folder named 'accounts' has been created and contains 100 SA. Now, how do you want to add these SA to your TD? \n"
					echo -e "1) Directly add them to the TD \n"
					echo -e "2) Make a Google Group and add all SA to it \n"
					while true ; do
						read -p "Enter your choice: " way
						case $way in
							"1")
								echo "Enter your Team Drive id"
								echo -e "(HINT- If your TD link is like 'https://drive.google.com/drive/folders/0ACYsMW75QbTSUk9PVA' then your TD id = 0ACYsMW75QbTSUk9PVA \n"
								read -p "TD id: " id
								python3 add_to_team_drive.py -d $id
								echo -e "Now you can goto your TD and see that 100 SA have been added \n"
								echo -e "Don't forget to set USE_SERVICE_ACCOUNTS to 'True' \n"
								break
							;;
							"2")
								cd accounts
								grep -oPh '"client_email": "\K[^"]+' *.json > emails.txt
								cd -
								echo -e "For that, follow TUTORIAL 3 given in this post: https://telegra.ph/Deploying-your-own-Mirrorbot-10-19#TUTORIAL-3 \n"
								for (( ; ; ))
								do
									read -p "After completing Tutorial, delete email.txt and Press y : " tut
									if [ $tut = y -o $tut = Y ] ; then
										break
									else
										echo -e "Then complete it first! \n"
									fi
								done
								break
							;;
							*)
								echo -e "Invalid choice \n"
							;;
						esac
					done
				fi
				if [ $sa = 3 ] ; then
					echo -e "\nNo problem, lets proceed further \n"
				break
				fi
				
				for (( ; ; ))
				do
					read -p "Confirm that you have filled all required vars in config.env by pressing y : " conf
					if [ $conf = y -o $conf = Y ] ; then
						echo -e "\nSo lets proceed further \n"
						echo
						echo -e "Now we will push this repo to heroku, for that \n"
						read -p "Enter the mail which you used for heroku account: " mail
						read -p "Enter your name: " name
						echo -e "\nIt is suggested to deploy bot more than 1 time as it ensures that Heroku does not suspend app."
						echo -e "For safety, app will be deployed 2 times. \n"
						sleep 3
						heroku git:remote -a $bname
						heroku stack:set container -a $bname
						git add -f .
						git config --global user.email "$mail"
						git config --global user.name "$name"
						git commit -m "Deploy number 1"
						git push heroku master --force
						heroku apps:destroy -c $bname
						echo -e "\nDeploy number 2"
						sleep 3
						heroku create $bname
						heroku git:remote -a $bname
						heroku stack:set container -a $bname
						git add -f .
						git config --global user.email "$mail"
						git config --global user.name "$name"
						git commit -m "Deploy number 2"
						git push heroku master --force
						heroku ps:scale web=0 -a $bname
						heroku ps:scale web=1 -a $bname
					break
					else 
						echo -e "Then do it first! \n"
					fi
				done
			break
		;;
		"2")
                echo -e "Firstly we will login to heroku \n"
				echo
				for (( ; ; ))
				do
					echo -e "Enter your Heroku credentials: \n"
					heroku login -i
					status=$?
					if test $status -eq 0; then
						echo -e "Signed in successfully \n"
					break
					fi
					echo -e "Invalid credentials, try again \n"
				done
				for (( ; ; ))
				do
					read -p "After adding credentials.json, token.pickle, SA folder (optional) and all necessary vars in config.env, press y: " req
					if [ $req = y -o $req = Y ] ; then
						for (( ; ; ))
						do
							read -p "Enter unique appname for your bot: " bname
							heroku create $bname
							status=$?
							if test $status -eq 0; then
								echo -e "App created successfully \n"
							break
							fi
						echo -e "Appname is already taken, choose another one \n"
						done
						echo -e "Now we will push this repo to heroku, for that \n"
						read -p "Enter the mail which you used for heroku account: " mail
						read -p "Enter your name: " name
						echo -e "\nIt is suggested to deploy bot more than 1 time as it ensures that Heroku does not suspend app."
						echo -e "For safety, app will be deployed 2 times. \n"
						sleep 3
						heroku git:remote -a $bname
						heroku stack:set container -a $bname
						git add -f .
						git config --global user.email "$mail"
						git config --global user.name "$name"
						git commit -m "Deploy number 1"
						git push heroku master --force
						heroku apps:destroy -c $bname
						echo -e "\nDeploy number 2"
						sleep 3
						heroku create $bname
						heroku git:remote -a $bname
						heroku stack:set container -a $bname
						git add -f .
						git config --global user.email "$mail"
						git config --global user.name "$name"
						git commit -m "Deploy number 2"
						git push heroku master --force
						heroku ps:scale web=0 -a $bname
						heroku ps:scale web=1 -a $bname
				break
					else
						echo -e "Then do add it first! \n"
					fi
				done
			break
            ;;
			"3")
				echo -e "\nFirst, we will login to heroku"
				echo
				for (( ; ; ))
				do
					echo -e "Enter your Heroku credentials: \n"
					heroku login -i
					status=$?
					if test $status -eq 0; then
						echo -e "Signed in successfully \n"
					break
					fi
					echo -e "Invalid credentials, try again \n"
				done
				
				for (( ; ; ))
						do
							read -p "Enter unique appname for your bot: " bname
							heroku create $bname
							status=$?
							if test $status -eq 0; then
								echo -e "App created successfully \n"
							break
							fi
						echo -e "Appname is already taken, choose another one \n"
						done
				heroku apps:destroy -c $bname
				echo -e "Now use this appname in BASE_URL_OF_BOT var like https://appname.herokuapp.com"
				break
			;;
            "4")
                read -p "Enter commit description in one line: " c_des
                git add -f .
                git commit -m "$c_des"
                git push heroku master --force
		break
            ;;
            *)
                echo -e "Invalid Choice \n"
            ;;
	esac
done
echo "Task completed successfully"

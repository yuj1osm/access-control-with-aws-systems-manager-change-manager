import boto3
from datetime import datetime, timedelta
import os
import traceback


def check_group(user_name, ctime_jst, client_iam):

    try:
        user_tags = client_iam.list_user_tags(UserName=user_name)['Tags']
        expired_group_list = [tag_json.get('Key') for tag_json in user_tags if datetime.strptime(tag_json['Value'], '%Y%m%d%H%M') < ctime_jst]

        for group_name in expired_group_list:
            client_iam.untag_user(UserName=user_name, TagKeys=([group_name]))
            client_iam.remove_user_from_group(UserName=user_name, GroupName=group_name)
            
        return expired_group_list
        
    except Exception:
        err_msg = traceback.format_exc()
        raise ValueError(err_msg)

def lambda_handler(event,context):

    # Declare local valiable for message
    msg = ''
    err_msg =''
    header_msg = ''
    body_msg = ''
    send_msg = ''
    
    # Get JST Current Time
    ctime_jst = datetime.now() + timedelta(hours=9)

    # Get IAM User List
    client_iam = boto3.client('iam')
    list_users = client_iam.list_users()
    list_user_names = [user_name['UserName'] for user_name in list_users['Users']]
    
    # Detach Policy and Untag from IAM User, if TTL has expired
    for user_name in list_user_names:
        try:
            expired_group_list = check_group(user_name, ctime_jst, client_iam)
            if (len(expired_group_list)) > 0:
                msg += user_name + " -> " + ', '.join(expired_group_list) + "\n"
            
        except Exception as raised_err:
            err_msg += user_name + " -> " + str(raised_err) + "\n"
            pass

    # Generate a message for SNS
    header_msg += """Change Managerの定期チェック通知です。
下記のドキュメントを参考に対応をしてください。
<ドキュメントのURL>\n
"""
    
    if len(msg) > 0:
        body_msg += "1)Change Managerで申請された終了時刻を過ぎていますが、終了申請の承認が確認できなかったため、以下のユーザを期限切れのグループから離脱させました。\n"
        body_msg += msg + "\n"

    if len(err_msg) > 0:
        body_msg += "2)以下のユーザのタグとグループの確認プロセスに異常が見られました。権限が剝奪できない可能性があるのでエラーを確認し対応してください。\n"
        body_msg += err_msg +"\n"

    # Send a message by SNS
    if len(body_msg) > 0:
        send_msg = header_msg + body_msg
        #print(send_msg)
        
        topic_arn = os.environ['topic_arn']
        subject = 'Check User Group Report'

        client_sns = boto3.client('sns')
        response = client_sns.publish(
            TopicArn=topic_arn,
            Message=send_msg,
        Subject=subject
        )
    
    return
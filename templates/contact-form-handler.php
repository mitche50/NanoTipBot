<?php
    use PHPMailer\PHPMailer\PHPMailer;
    use PHPMailer\PHPMailer\Exception;
    require 'PHPMailer/src/Exception.php';
    require 'PHPMailer/src/PHPMailer.php';
    require 'PHPMailer/src/SMTP.php';
	$configs = include('config.php');
	
	$email_address = $_POST['email']; 
	$errors = '';
	
	if(empty($_POST['email']) || 
	   empty($_POST['message'] || empty($_POST['username'])))
	{
		$errors .= "\n Error: all fields are required";
	}
	if (!preg_match("/^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,3})$/i", $email_address)){
		$errors .= "\n Error: Invalid email address";
	}
	if( empty($errors))
	{
		$mail = new PHPMailer();
		$mail->IsSMTP();
		
		$mail->SMTPDebug = 0; 
		$mail->SMTPAuth = true;
		$mail->SMTPSecure = "tls";
		$mail->Host = "smtp.gmail.com";
		$mail->Port = 587; 
		
		$mail->Username = $configs['mail_address'];
		$mail->Password = $configs['mail_pw'];
		
		$mail->CharSet = 'windows-1250';
		$mail->SetFrom ('noreply@nanotipbot.com', 'Nano Tip Bot');
		$mail->Subject = "Contact form submission: $email_address";
		$mail->ContentType = 'text/plain'; 
		$mail->IsHTML(true);
	 
		
		$message = $_POST['message']; 
		$username = $_POST['username'];


        $email_body = '<html><body>';
		$email_body .= '<h1>You have received a new message.</h1>';
		$email_body .= '<table rules="all" frame="box" style="border-color: #666;" cellpadding="10">';
		$email_body .= "<tr><td><strong>Email:</strong> </td><td>" . $email_address . "</tr></td>";
		$email_body .= "<tr><td><strong>Username:</strong> </td><td>" . $username . "</tr></td>";
		$email_body .= "<tr><td><strong>Message:</strong> </td><td>" . $message . "</tr></td>";
		$email_body .= "</table>";
		$email_body .= "</body></html>";
		
		$mail->Body = $email_body;
		$mail->AddAddress ($configs['destination'], 'Andrew Mitchell');
		
		if(!$mail->Send()) 
		{
			$error_message = "Mailer Error: " . $mail->ErrorInfo;
		} else {
		//redirect to the 'thank you' page
		header('Location: contact-form-thank-you.html');
		}
	}else{
		echo $errors;
	}
?>

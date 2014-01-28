<?php

$base = "http://wsrc.game-host.org";  //set this to the url you want to scrape

$url = $base . $_SERVER['REQUEST_URI'];
$url = str_replace("_proxy", "", $url);
$url = str_replace(".php", "", $url);

$curlSession = curl_init();
curl_setopt ($curlSession, CURLOPT_URL, $url);
curl_setopt ($curlSession, CURLOPT_HEADER, 1);

$mydomain = 'http://'.$_SERVER['HTTP_HOST'];


if($_SERVER['REQUEST_METHOD'] == 'POST'){
	curl_setopt ($curlSession, CURLOPT_POST, 1);
	curl_setopt ($curlSession, CURLOPT_POSTFIELDS, $_POST);
}

curl_setopt($curlSession, CURLOPT_RETURNTRANSFER,1);
curl_setopt($curlSession, CURLOPT_TIMEOUT,30);
//Send the request and store the result in an array
$response = curl_exec ($curlSession);

// Check that a connection was made
if (curl_error($curlSession)){
        // If it wasn't...
        print curl_error($curlSession);
} else {

	//clean duplicate header that seems to appear on fastcgi with output buffer on some servers!!
	$response = str_replace("HTTP/1.1 100 Continue\r\n\r\n","",$response);

	$ar = explode("\r\n\r\n", $response, 2); 


	$header = $ar[0];
	$body = $ar[1];

	//handle headers - simply re-outputing them
	$header_ar = split(chr(10),$header); 
	foreach($header_ar as $k=>$v){
		if(!preg_match("/^Transfer-Encoding/",$v)){
			$v = str_replace($base,$mydomain,$v); //header rewrite if needed
			header(trim($v));
		}
	}

  //rewrite all hard coded urls to ensure the links still work!
	$body = str_replace($base,$mydomain,$body);

	print $body;

}

curl_close ($curlSession);


?>


<?php
   ob_start();
   session_start();
   unset($_SESSION["username"]);
   unset($_SESSION["password"]);
   unset($_SESSION["valid"]);
   echo 'Session logged out';
   header('Refresh: 2; URL = index.php');
?>
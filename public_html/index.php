<?php
require_once __DIR__ . '/../vendor/autoload.php';

/****************************************** */
/* streammonitor.php
/* This is a web interface for the stream monitor.  It allows the user to view the status of the streams, and to modify the configuration of the streams and users.
/* It is a component of the streammonitor system, for a set of tools for monitoring audio streams for silence, black, and freeze frames
/* Author: Scott McGrath (scott@smcgrath.com)
/****************************************** */


ob_start();
// session_start(['cookie_lifetime' => 86400]);
session_start();
// error_reporting(E_ALL);
// ini_set("display_errors", 1);
?>

<html lang="en">

<head>
   <title>Stream Monitor</title>
   <!-- Required meta tags -->
   <meta charset="utf-8">
   <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

   <!-- Bootstrap CSS -->
   <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css" integrity="sha384-ggOyR0iXCbMQv3Xipma34MD+dH/1fQ784/j6cY/iJTQUOhcWr7x9JvoRxT2MZw1T" crossorigin="anonymous">

   <!-- JQuery -->
   <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>

   <link rel="stylesheet" href="style.css">
</head>

<body>

   <h1>Stream Monitor</h1>
   <?php
   $msg = '';
   $db_name = "streammon";
   // Load the connection string from config.py in the parent directory
   $conn_string = read_from_config("MONGO_CONNECTION_STRING");

   // Check it for validity
   if (strpos($conn_string, "mongodb://") !== false) {
      // echo "Using connection string: $conn_string<br>\n";
   } else {
      echo "FATAL: The connection string in config.py is invalid!<br>\n";
      exit;
   }

   // $log_file_dir = "/home/streammon/logs";
   // $log_file_dir = "/logs";
   $log_file_dir = __DIR__ . '/logs';  // /home/streammon/public_html/logs
   $max_monitors = 7;

   // print "session isset= ".isset($_SESSION['valid'])."<br>\n";
   if (empty($_SESSION['username'])) {

      if (isset($_POST['login']) && !empty($_POST['username']) && !empty($_POST['password'])) {

         // We don't have a session established, and they are trying to login.  Try to connect and auth
         try {

            // connect to mongodb
            $conn = new MongoDB\Client($conn_string);
            $users = $conn->$db_name->users;


            if ($users != null) {


               $userName = $_POST['username'];
               $userPass = $_POST['password'];

               // Authentication involves seeing if we can find and entry in the users collection that matches the post values
               // $user = $users->findOne(array('username'=> $userName, 'password'=> $userPass, 'enabled'=>'1'));
               $user = $users->findOne(array('username' => $userName, 'password' => $userPass));

               if ($user != null) {
                  echo $user->name . " login success <img class=\"loader_img\" src=\"loader2.gif\">\n";

                  //Set up the session
                  $_SESSION['valid'] = true;
                  $_SESSION['timeout'] = time();
                  $_SESSION['username'] = $userName;
                  do_refresh();
               } else {
                  echo "The authentication info you specified was invalid.<br>\n";
               }
            } // Couldn't find the collection "users"
            else {
               echo "FATAL: Collection users missing!<br>\n";
            }
         } catch (MongoConnectionException $e) {
            die('Error connecting to MongoDB server');
         } catch (MongoException $e) {
            die('Error: ' . $e->getMessage());
         }
      } // If we have POST stuff needed to log in

   }  // If no session / is invalid



   else {      // Session is valid

      /**************************************************** Control code based on REQUEST actions *****************************/


      /****  Display Users editing form ****/
      if ($_GET['action'] == "users") {
         print "<h2>manage users</h2>\n";
         display_users_for_modify();
         do_menu();
      }

      /****  Display streams editing form ****/
      else if ($_GET['action'] == "streams") {
         print "<h2>manage streams</h2>\n";
         display_streams_for_modify();
         do_menu();
      }

      /****  Display alerts history ****/
      else if ($_GET['action'] == "alerts") {

         display_alert_history();
         do_menu();
      }






      /**** Receive submitted stream edits ****/
      else if ($_GET['action'] == "modify_streams") {
         print "Updating stream configs...<br>\n";
         // var_dump($_REQUEST);
         print "<br>\n";

         // Sanitize and update the database with received values

         // Loop through the configured streams and update where needed                  
         // $conn = new MongoDB\Client($conn_string);
         $conn = new MongoDB\Client($conn_string);
         $stream_configs = $conn->$db_name->stream_configs;

         $cursor = $stream_configs->find();

         // Iterate through the received stream configs
         for ($i = 0; $i < count($_POST["title"]); $i++) {
            // Delete if there is no title
            if (strlen($_POST["title"][$i]) > 0) {

               if (strlen($_POST["id"][$i]) > 0) {
                  // update a matching database entry

                  // Find the doc with the same id and updated it
                  $doc = $stream_configs->findOne(['_id' => new MongoDB\BSON\ObjectID($_POST["id"][$i])]);

                  // Update each attribute on this doc, using if statements for sanitization
                  print "Updating " . $doc->title . " with title=" . $_POST["title"][$i] . "<br>\n";
                  print "Updating " . $doc->title . " with uri=" . $_POST["uri"][$i] . "<br>\n";
                  print "Updating " . $doc->title . " with enabled=" . $_POST["enabled"][$i] . "<br>\n";
                  print "Updating " . $doc->title . " with audio=" . $_POST["audio"][$i] . "<br>\n";
                  // $stream_configs->updateOne(['_id' => new MongoDB\BSON\ObjectID($_POST["id"][$i])], ['title' => $_POST['title'], 'uri' => $_POST['uri'], 'enabled' => $_POST["enabled"]], ["upsert"] );

                  $filter = [
                     '_id' => new MongoDB\BSON\ObjectID($_POST["id"][$i])
                  ];

                  $update = [
                     '$set' => [
                        'title' => $_POST["title"][$i],
                        'uri' => $_POST["uri"][$i],
                        'audio' => $_POST["audio"][$i],
                        'enabled' => $_POST["enabled"][$i]
                     ]
                  ];
                  $stream_configs->updateOne($filter, $update, ["upsert" => false]);
               } // End up updating an existing stream entry

               else {
                  // Create a new entry
                  print "Creating " . $doc->title . " with title=" . $_POST["title"][$i] . "<br>\n";
                  print "Creating " . $doc->title . " with uri=" . $_POST["uri"][$i] . "<br>\n";
                  print "Creating " . $doc->title . " with enabled=" . $_POST["enabled"][$i] . "<br>\n";
                  // $stream_configs->updateOne(['_id' => new MongoDB\BSON\ObjectID($_POST["id"][$i])], ['title' => $_POST['title'], 'uri' => $_POST['uri'], 'enabled' => $_POST["enabled"]], ["upsert"] );

                  $insert = [
                     'title' => $_POST["title"][$i],
                     'uri' => $_POST["uri"][$i],
                     'audio' => $_POST["audio"][$i],
                     'enabled' => $_POST["enabled"][$i]
                  ];
                  $stream_configs->insertOne($insert);
               }
            }  // End of stuff to do if the title is not blank


            else {
               // If the title is blank, nuke this stream document.
               print "Pruning empty entries... " . $_POST["id"][$i] . "<br>\n";
               $stream_configs->deleteOne(['_id' => new MongoDB\BSON\ObjectID($_POST["id"][$i])]);
            }
         }

         // Reset all the running streams
         restart();



         do_refresh();  // Move on to the dashboard 
      }




      /**** Receive submitted users edits ****/
      else if ($_GET['action'] == "modify_users") {
         print "Updating users...<br>\n";
         // var_dump($_REQUEST);
         print "<br>\n";

         // Sanitize and update the database with received values

         // Loop through the configured streams and update where needed                  
         // $conn = new MongoDB\Client($conn_string);
         $conn = new MongoDB\Client($conn_string);
         $users = $conn->$db_name->users;

         $cursor = $users->find();

         $update_successful = 1;

         // Iterate through the received users
         for ($i = 0; $i < count($_POST["username"]); $i++) {
            // Make updates if there is a username
            if (strlen($_POST["username"][$i]) > 0) {
               // Verify the password entries match
               if (strcmp($_POST["password1"][$i], $_POST["password2"][$i]) == 0) {

                  if (strlen($_POST["id"][$i]) > 0) {
                     // update a matching database entry

                     // Find the doc with the same id and updated it
                     $doc = $users->findOne(['_id' => new MongoDB\BSON\ObjectID($_POST["id"][$i])]);

                     // Update each attribute on this doc, using if statements for sanitization
                     // print "Updating ".$doc->username." with username=".$_POST["username"][$i]."<br>\n";
                     // print "Updating ".$doc->username." with pushover=".$_POST["pushover"][$i]."<br>\n";
                     // print "Updating ".$doc->username." with enabled=".$_POST["enabled"][$i]."<br>\n";
                     print "Updating " . $doc->username . "...<br>\n";

                     // $users->updateOne(['_id' => new MongoDB\BSON\ObjectID($_POST["id"][$i])], 
                     // ['$set' => ['enabled' => $_POST["enabled"][$i], 'username' => $_POST["username"][$i], 
                     // 'pushover' => $_POST["pushover"][$i]]],['upsert']);  // Upsert so we may extend the schema on the fly


                     $users->updateOne(
                        ['_id' => new MongoDB\BSON\ObjectID($_POST["id"][$i])],
                        ['$set' => [
                           'enabled' => $_POST["enabled"][$i], 'username' => $_POST["username"][$i],
                           'pushover_id' => $_POST["pushover_id"][$i],
                           'pushover_token' => $_POST["pushover_token"][$i],
                           'password' => $_POST["password1"][$i]
                        ]],
                        ['upsert']
                     );  // Upsert so we may extend the schema on the fly

                  } // End of updating an existing user

                  else {
                     // Create a new entry
                     print "Creating " . $doc->username . " with username=" . $_POST["username"][$i] . "<br>\n";
                     print "Creating " . $doc->username . " with pushover_id=" . $_POST["pushover_id"][$i] . "<br>\n";
                     print "Creating " . $doc->username . " with pushover_token=" . $_POST["pushover_token"][$i] . "<br>\n";
                     print "Creating " . $doc->username . " with enabled=" . $_POST["enabled"][$i] . "<br>\n";

                     $users->insertOne(['enabled' => $_POST["enabled"][$i], 'username' => $_POST["username"][$i], 'pushover_id' => $_POST["pushover_id"][$i], 'pushover_token' => $_POST["pushover_token"][$i], 'password' => $_POST["password1"][$i]]);
                  }
               } // End of stuff to do if the password entries match

               else {
                  $update_successful = 0;
                  print $_POST["username"][$i] . ": password entries did not match<br>\n";
                  print "<a href=\"?action=users\">Retry</a><br><br>\n";
               }
            }  // End of stuff to do if the username is not blank


            else {
               // If the username is blank, nuke this user document.
               print "Pruning empty entries... " . $_POST["id"][$i] . "<br>\n";
               $users->deleteOne(['_id' => new MongoDB\BSON\ObjectID($_POST["id"][$i])]);
            }
         }

         // Reset all the running stream monitors because notification info may have changed
         restart();



         if ($update_successful) {
            do_refresh();
         }  // Move on to the dashboard if the update didn't have any errors
      }


















      /****  Monitor dashboard ****/
      else  // No action specified, so display the monitor dashboard
      {

         // var_dump($_REQUEST);

         echo "logged in as " . $_SESSION['username'] . "<br>\n";
         echo '<div class = "container dashboard">';

         //display_running_stream_info();

         do_refresh();

         print "<br><br>\n";
         list_configured_streams();
         print "<br>\n";
         do_menu();
      }
   }



   function do_menu()
   {

      print '
   <br>
               <a href="?">dashboard</a>
      <br>
               <a href="?action=streams">modify streams</a>
      <br>
               <a href="?action=users">modify users</a>
      <br>
               <a href="?action=alerts">alert history</a>
      <br>
               <a href="logout.php" title="Logout">logout</a>
';
   }







   /* The main stream monitor function, displays the streams and their status */
   function list_configured_streams()
   {
      global $db_name;
      global $conn_string;
      $conn = new MongoDB\Client($conn_string);
      // global $conn;

      $stream_configs = $conn->$db_name->stream_configs;

      $cursor = $stream_configs->find();

      print "<table border=\"1\" width=\"100%\">";
      // print "<tr><td></td><td class=\"main_title\">Title</td>  <td class=\"main_uri\">URI</td>  <td class=\"main_status\">Status</td>  <td class=\"main_enabled\">Enabled</td></tr>\n";
      print "<tr><td>Thumbnail</td><td class=\"main_title\">Title</td>  <td class=\"main_uri\">URI</td>  <td class=\"main_status\">Status</td> </tr>\n";
      foreach ($cursor as $stream) {
         if ($stream->enabled != 0) {
            print "<tr>";
            print "<td class=\"main_thumbnail\">";
            display_frame_image($stream->title);
            print "</td>";
            print "<td class=\"main_title\">" . $stream->title . "</td>\n";
            print "<td class=\"main_uri\"><a href=\"" . $stream->uri . "\" target=\"_blank\">" . $stream->uri . "</a></td>\n";
            print "<td class=\"main_status\">";
            print stream_running_info($stream->title);
            print "</td>\n";
            echo "</tr>\n";
         }     // Only include this stream if it is enabled.
      }

      print "</table>\n";
   }


   function display_frame_image($stream_title)
   {
      // print "Displaying image for $stream_title\n";
      global $db_name;
      global $conn_string;
      $conn = new MongoDB\Client($conn_string);
      $stream_images = $conn->$db_name->stream_images;
      $cursor = $stream_images->findOne(['stream' => $stream_title]);

      $imagebody = $cursor->data;
      print '<img src="data:jpeg;base64,' . $imagebody . '" class="stream-thumbnail" / style="display: block; width: 100%; height: auto;">';
      print "<br>\n";
      print $cursor->timestamp;
   }




   /* Prints a form with an editable table of all configured streams in DB  */
   function display_streams_for_modify()
   {
      print "<form action=\"?action=modify_streams\" method=\"post\">\n";

      global $db_name;
      global $conn_string;
      global $max_monitors;

      $conn = new MongoDB\Client($conn_string);
      $stream_configs = $conn->$db_name->stream_configs;

      $cursor = $stream_configs->find();

      print "<table border=\"1\" width=\"100%\">\n";
      print "<tr><td>Title</td>  <td>URI</td>  <td>AudioOnly</td><td>Enabled</td><td>Delete</td></tr>\n";


      $i = 0;

      foreach ($cursor as $stream) {
         $i++;
         print "<tr>";
         // print "<td>".var_dump($stream)."</td>\n"; 
         //print "<br>\n"; 
         // print "<td><input type=\"text\" name=\"".$stream->title."[title]\" value=\"".$stream->title."\"></td>\n";
         print "<td><input type=\"text\" name=\"title[]\" multiple=\"yes\" class=\"" . $stream->_id . "\" value=\"" . $stream->title . "\"></td>\n";
         print "<td><textarea name=\"uri[]\" multiple=\"yes\" cols=\"50\" class=\"" . $stream->_id . "\">" . $stream->uri . "</textarea></td>\n";
         print "<td>\n";
         /* A hidden control will have the mongodb objectID */
         print '<input type="hidden" name="id[]" multiple="yes" value="' . $stream->_id . '">';

         /* Another hidden control will represent the value of "enabled" as 0 or 1, to keep the POST array aligned */

         // Get the value of audio for this stream  (if 1, the type of the stream is audio instead of video)
         if ($stream->audio == "1") {
            print '<!-- Rounded switch -->
               <label class="switch">
               <input type="hidden" name="audio[]" multiple="yes" class="' . $stream->_id . '" value="1">
               <input type="checkbox" name="audio_checkbox[]" multiple="yes" class="' . $stream->title . '" checked>                  
               <span class="slider round"></span>
               </label>';
         } else {
            print '<!-- Rounded switch -->
            <label class="switch">
            <input type="hidden" name="audio[]" multiple="yes" class="' . $stream->_id . '" value="0">  
            <input type="checkbox" name="audio_checkbox[]" multiple="yes" class="' . $stream->_id . '">  
            <span class="slider round"></span>
            </label>';
         }
         print "</td>";

         print "<td>\n";
         // Get the value of "enabled" for this stream        
         if ($stream->enabled != 0) {
            print '<!-- Rounded switch -->
               <label class="switch">
               <input type="hidden" name="enabled[]" multiple="yes" class="' . $stream->_id . '" value="1">
               <input type="checkbox" name="enabled_checkbox[]" multiple="yes" class="' . $stream->title . '" checked>                  
               <span class="slider round"></span>
               </label>';
         } else {
            print '<!-- Rounded switch -->
            <label class="switch">
            <input type="hidden" name="enabled[]" multiple="yes" class="' . $stream->_id . '" value="0">  
            <input type="checkbox" name="enabled_checkbox[]" multiple="yes" class="' . $stream->_id . '">  
            <span class="slider round"></span>
            </label>';
         }
         print "</td>";


         print '<td><img src="trash.png" onclick="$(\'.' . $stream->_id . '\').val(\'\');   $(\'.' . $stream->_id . '\').prop(\'checked\', false);" width="35"></td>';
         echo "</tr>\n";
      }  // End of foreach stream


      // Extra blank line for a new stream if we have less than max_monitors configured. This is totally hackable, but whatever.
      if ($i < $max_monitors) {

         print "<tr>";
         print "<td><input type=\"text\" name=\"title[]\" multiple=\"yes\"></td>\n";
         print "<td><textarea name=\"uri[]\" multiple=\"yes\" cols=\"50\"></textarea></td>\n";

         print "<td>\n";
         print '<!-- Rounded switch -->
       <label class="switch">
       <input type="hidden" name="audio[]" multiple="yes" id="" value="0">  
       <input type="checkbox" name="audio_checkbox[]" multiple="yes">
          
       <span class="slider round"></span>
       </label>';

         print "</td>";

         print "<td>\n";
         print '<!-- Rounded switch -->
       <label class="switch">
       <input type="hidden" name="enabled[]" multiple="yes" id="" value="0">  
       <input type="checkbox" name="enabled_checkbox[]" multiple="yes">
          
       <span class="slider round"></span>
       </label>';

         print "</td>";
         print "<td></td>";
         echo "</tr>\n";
      }

      print "</table>\n";
      print "<input type=\"submit\" value=\"Update\">\n";
      print "</form>\n";


      print '

         <script>
         /* This synchronizes the value of the corresponding hidden control for the enabled and type checkboxes */
         $(\'input[type="checkbox"]\').on(\'change\', function(e){
            //console.log("Blah");
        if($(this).prop(\'checked\'))
        {
            $(this).val(1);         
            $(this).prev().val(1);
        } else {
            $(this).val(0);
            $(this).prev().val(0);
        }
         });

         // Add code to reset values on same line as delete icon


      </script>

   ';
   }


   function display_alert_history()
   {
      global $db_name;
      global $conn_string;

      $mynumber = 10;

      $conn = new MongoDB\Client($conn_string);
      $alerts = $conn->$db_name->stream_alerts;

      $filter  = [];
      $options = ['limit' => $mynumber, 'sort' => ['timestamp' => -1]];


      $cursor = $alerts->find($filter, $options);

      print "<h2>last " . $mynumber . " alerts</h2>\n";
      print "<table border=\"1\">\n";
      print "<tr><td class=\"alerts_image\"></td><td class=\"alerts_datetime\">Date/Time</td><td class=\"alerts_stream\">Stream</td><td class=\"alerts_description\">Alert</td></tr>\n";


      $i = 0;

      foreach ($cursor as $alert) {
         $i++;
         print "<tr>";
         print "<td class=\"alerts_image\">";
         print '<img src="data:jpeg;base64,' . $alert->image . '" class="stream-thumbnail" />';
         print "</td>";
         print "<td class=\"alerts_datetime\" >$alert->timestamp</td>\n";
         print "<td class=\"alerts_stream\" >$alert->stream</td>\n";
         print "<td class=\"alerts_description\" >$alert->alert</td>\n";

         /* A hidden control will have the mongodb objectID */
         print '<input type="hidden" name="id[]" multiple="yes" value="' . $alert->_id . '">';
         echo "</tr>\n";
      }  // End of foreach alert


      print "</table>\n";
   }



   /* Prints a form with an editable table of all configured users in DB  */
   function display_users_for_modify()
   {
      print "<form action=\"?action=modify_users\" method=\"post\">\n";

      global $db_name;
      global $conn_string;
      global $max_monitors;

      $conn = new MongoDB\Client($conn_string);
      $users = $conn->$db_name->users;

      $cursor = $users->find();

      print "<table border=\"1\" width=\"100%\">\n";
      print "<tr><td class=\"users_username\">Username</td>  <td> Password</td> <td> Password (verify) </td> <td>Pushover User ID</td><td>Pushover Token</td>  <td>Notifications</td><td>Delete</td></tr>\n";


      $i = 0;

      foreach ($cursor as $user) {
         $i++;
         print "<tr>";
         print "<td class=\"users_username\" ><input type=\"text\" name=\"username[]\" multiple=\"yes\" class=\"" . $user->_id . "\" value=\"" . $user->username . "\"></td>\n";
         print "<td class=\"users_password\"><input type=\"password\" name=\"password1[]\" multiple=\"yes\" class=\"" . $user->_id . "\" value=\"" . $user->password . "\"></td>\n";
         print "<td class=\"users_password\"><input type=\"password\" name=\"password2[]\" multiple=\"yes\" class=\"" . $user->_id . "\" value=\"" . $user->password . "\"></td>\n";
         print "<td class=\"users_pushover\"><input type=\"text\" name=\"pushover_id[]\" multiple=\"yes\" class=\"" . $user->_id . "\" value=\"" . $user->pushover_id . "\"></td>\n";
         print "<td class=\"users_pushover\"><input type=\"text\" name=\"pushover_token[]\" multiple=\"yes\" class=\"" . $user->_id . "\" value=\"" . $user->pushover_token . "\"></td>\n";
         print "<td class=\"users_enabled\">\n";
         /* A hidden control will have the mongodb objectID */
         print '<input type="hidden" name="id[]" multiple="yes" value="' . $user->_id . '">';
         /* Another hidden control will represent the value of "enabled" as 0 or 1, to keep the POST array aligned */
         // Get the value of "enabled" for this user        
         if ($user->enabled != 0) {
            print '<!-- Rounded switch -->
               <label class="switch">
               <input type="hidden" name="enabled[]" multiple="yes" class="' . $user->_id . '" value="1">
               <input type="checkbox" name="enabled_checkbox[]" multiple="yes" class="' . $user->_id . '" checked>                  
               <span class="slider round"></span>
               </label>';
         } else {
            print '<!-- Rounded switch -->
            <label class="switch">
            <input type="hidden" name="enabled[]" multiple="yes" class="' . $user->_id . '" value="0">  
            <input type="checkbox" name="enabled_checkbox[]" multiple="yes" class="' . $user->_id . '">  
            <span class="slider round"></span>
            </label>';
         }
         print "</td>";
         print '<td class=\"users_delete\"><img src="trash.png" onclick="$(\'.' . $user->_id . '\').val(\'\');   $(\'.' . $user->_id . '\').prop(\'checked\', false);" width="35"></td>';
         echo "</tr>\n";
      }  // End of foreach user


      // Extra blank line for a new user        
      print "<tr>";
      print "<td class=\"users_username\"><input type=\"text\" name=\"username[]\" multiple=\"yes\"></td>\n";
      print "<td class=\"users_password\"><input type=\"password\" width=\"10\" name=\"password1[]\" multiple=\"yes\"></td>\n";
      print "<td class=\"users_password\"><input type=\"password\" width=\"10\" name=\"password2[]\" multiple=\"yes\"></td>\n";
      print "<td class=\"users_pushover\"><input type=\"text\" name=\"pushover_id[]\" multiple=\"yes\"></td>\n";
      print "<td class=\"users_pushover\"><input type=\"text\" name=\"pushover_token[]\" multiple=\"yes\"></td>\n";
      print "<td class=\"users_enable\">\n";
      print '<!-- Rounded switch -->
    <label class="switch">
    <input type="hidden" name="enabled[]" multiple="yes" id="" value="0">  
    <input type="checkbox" name="enabled_checkbox[]" multiple="yes">
       
    <span class="slider round"></span>
    </label>';

      print "</td>";
      print "<td class=\"users_delete\"></td>";
      echo "</tr>\n";


      print "</table>\n";
      print "<input type=\"submit\" value=\"Update\">\n";
      print "</form>\n";


      print '
         <script>
         $(\'input[type="checkbox"]\').on(\'change\', function(e){
            console.log("Blah");
        if($(this).prop(\'checked\'))
        {
            $(this).val(1);         
            $(this).prev().val(1);
        } else {
            $(this).val(0);
            $(this).prev().val(0);
        }
         });

         // Add code to reset values on same line as delete icon


      </script>

   ';
   }



   // Returns the status of given stream monitor from stream_reports collection in db
   function stream_running_info($stream_title)
   {
      global $conn_string;
      global $db_name;

      $conn = new MongoDB\Client($conn_string);
      $stream_reports = $conn->$db_name->stream_reports;

      $cursor = $stream_reports->findOne(['title' => $stream_title]);

      return $cursor->status;
   }



   /* Kills all stream receivers and monitors in a fairly undiscerning way */
   function restart()
   {
      // Sets the restart_due value to 1 in the "global_configs" collection only document
      global $db_name;
      global $conn_string;
      $conn = new MongoDB\Client($conn_string);
      $global_configs = $conn->$db_name->global_configs;

      $global_configs->updateOne(['global_configs' => '1'], ['$set' => ['restart_due' => '1']], ['upsert' => true]);
   }



   /* Turns on auto refresh client side */
   function do_refresh()
   {
      print "<img class=\"loader_img\" src=\"loader2.gif\">\n";
      header('Refresh: 2; URL = ?');
   }


   /* Deprecated. prints a table of all stream monitor processes found in PS */
   function display_running_stream_info()
   {
      global $conn_string;
      global $log_file_dir;

      $command = "ps aux |grep ffmpeg";
      exec($command, $ps_array, $retval);

      // Get the URLs of running ffmpeg instances 
      foreach ($ps_array as $line) {
         $pattern = "/\-i\ (.*?)\ /";
         // print "$line <br>\n";
         $matchCount  = preg_match($pattern, $line, $capture);
         // print "$capture[1]<br>\n";        
         // echo "<br>\n";
         if ($matchCount > 0) {
            $this_url = $capture[1];
            $streams_found[$this_url] = 1;
         }
      }

      $command = "ps aux |grep python2";
      exec($command, $ps_array, $retval);

      // Get the stream descriptions from running stream monitor instances
      foreach ($ps_array as $line) {
         $pattern = "/\-\-stream_uri\ (.*?)\ .*\-\-stream_desc (.*)/";
         // print "$line <br>\n";
         $matchCount = preg_match($pattern, $line, $capture);
         // print "$capture[1]<br>\n";        
         // echo "<br>\n";
         if ($matchCount > 0) {
            $this_url = $capture[1];
            $this_desc = $capture[2];
            if (array_key_exists($this_url, $streams_found)) {
               $streams_found[$this_url] = $this_desc;
            }
         }
      }

      do_refresh();
      print("Monitor is running for the following streams: \n<p></p>\n");
      echo "<table border=\"1\" style=\"border-collapse: collapse;\">\n";

      $conn = new MongoDB\Client($conn_string);
      $stream_configs = $conn->$db_name->stream_configs;

      foreach ($streams_found as $x => $x_value) {
         // echo "Key=" . $x . ", Value=" . $x_value;
         // echo "<tr><td>".$x_value  . "</td><td>" . $x . "</td>"."<td>".tailShell("$log_file_dir/$x_value.log",1)."</td>";
         echo "<tr><td>" . $x_value  . "</td><td>" . $x . "</td>" . "<td>" . "</td>";

         // Get the value of "enabled" for this stream        
         $this_stream = $stream_configs->findOne(array('title' => $x_value));
         if ($this_stream != null) {
            print $this_stream->enabled;
         } else {
            print "Couldn't find stream $x_value in the database<br>\n";
         }

         print '<td><!-- Rounded switch -->
      <label class="switch">
        <input type="checkbox" id="' . $x_value . '" checked="' . $enabled . '">
        <span class="slider round"></span>
      </label></td>';
         echo "</tr>\n";
      }
      echo "</table>\n";
   }   // show running streams function




   /* Returns the last line in the file */
   function tailShell($filepath, $lines = 1)
   {

      ob_start();

      $command = 'tail -'  . $lines . ' ' . escapeshellarg($filepath);
      // Greater need to sanitize $filepath here
      passthru($command, $error);

      return trim(ob_get_clean());
   }



   /* Reads the config parameters from config.py and returns them in an array */
   function read_from_config($parameter_name)
   {
      // echo "read_from_config():<br>\n";
      $config_file = fopen("../config.py", "r") or die("Unable to open config file!");
      $config_array = array();

      // Force uppercase for the parameter name
      $parameter_name = strtoupper($parameter_name);
      // echo "Searching for $parameter_name<br>\n";

      while (!feof($config_file)) {
         $line = fgets($config_file);
         // echo "$line<br>\n";

         if (strpos($line, $parameter_name) !== false) {
            $config_array = explode(" = ", $line);
            // Remove leading and trailing quotes
            $config_array[1] = trim($config_array[1]);
            $config_array[1] = trim($config_array[1], '"');
            // Return the value of the parameter that matches the given parameter name
            return $config_array[1];
         }
      }
   }
   ?>








   </div> <!-- /container -->

   <?php if (!$_SESSION["valid"]) { ?>
      <div class="login-container">

         <form class="form-signin" role="form" action="<?php echo htmlspecialchars($_SERVER['PHP_SELF']);
                                                         ?>" method="post">
            <h4 class="form-signin-heading"><?php echo $msg; ?></h4>
            <input type="text" class="form-control" name="username" placeholder="username" required autofocus></br>
            <input type="password" class="form-control" name="password" placeholder="password" required>
            <button class="btn btn-lg btn-primary btn-block" type="submit" name="login">Login</button>
         </form>


      </div>
   <?php } ?>

</body>

</html>
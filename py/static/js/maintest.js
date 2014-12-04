var selectedsong;
var settingsObj;
//var files;
	
function refreshPlaylistUL(data){
	var temp1="<li data-theme='b' data-role='list-divider'>Playlists</li>";
	$('#popupNewPlaylist').popup('close');
	for(var i=0;i<data.playlists.length;i++){
		temp1+="<li data-theme='d'><a class='playlist' href='#' id='"+data.playlists[i][1]+"'>"+data.playlists[i][0]+"</a></li>"
	}
	$('#playlistsul').html(temp1).listview('refresh');
}

var sliderTimer = null;
function updatePlaybackSlider(currentpos){
	if (sliderTimer) {
		clearTimeout(sliderTimer)
		sliderTimer = null
	}
	
    done = true;
	$('.slider').each(function(){		
		max = parseInt($(this).attr('max'), 10);		
		if (currentpos < max) {
		    done = currentpos == -1;
			try{$(this).val(currentpos).slider('refresh');}catch(e){}			
		}
	});
	
	if (!done) {
		sliderTimer = setTimeout(function(){updatePlaybackSlider(currentpos + 1)},1000);
	}
}

function getCurrentTrack(){
		$.ajax({
			type: 'POST',
			url: '/getvars',
			async: true,
			dataType:'json',
			success: function(data)
			{
				//data=JSON.parse(data);
				//console.log(data);
				
				if(data.currentsong!=''){
					$('.currentsong').html(data.currentsong);
					$('.currentpos').html(data.currentpos);
					$('.duration').html(data.duration);
					if(data.duration > 0) {
						$('.slider').attr('max',data.duration);
					} else {
						$('.slider').attr('max','100');
					}
					
					currentpos = parseInt(data.currentpos, 10)
					duration = parseInt(data.duration, 10)
					if (duration >= currentpos) {
						updatePlaybackSlider(currentpos)
					}
				}
				
				
				
				var temp='';
				for(var i=0;i<data.playlist.length;i++)
				{
					if(data.playlist[i]==data.playlistplaying)
					{
						temp+='<li data-song="'+data.playlist[i]+'" data-icon="audio"><a href="#">'+data.playlist[i]+'</a></li>';
					}
					else
					{
						temp+='<li data-song="'+data.playlist[i]+'">'+data.playlist[i]+'</li>';
					}
				}
				$(".playlistpanelul").html(temp);
				$(".playlistpanelul").each(function(){
					try{$(this).listview('refresh');;}catch(e){}
				});
			},
			complete:function()
			{
				// TODO(todd): Get an update after other events when we know a change is made.
				setTimeout(function(){getCurrentTrack()},10000);
			}
		});
		
	}
$(document).ready(function(){
	
		$.ajax({
			type: 'POST',
			url: '/ajax',
			async: true,
			data: 'option=5',
			success: function(data)
			{
				var ulVals='';
				settingsObj=JSON.parse(JSON.parse(data));
				for(temp in settingsObj){
					ulVals+='<li><a href="#'+temp+'" data-ajax="false">'+temp+'</a></li>';//console.log(temp)
					$('#tabs').append('<div id="'+temp+'" class="ui-body-d ui-content"></div>');
					for(temp2 in settingsObj[temp]){
						$('#'+temp).append('<div class="ui-field-contain"><label for="'+temp2+'">'+temp2+'</label><input name="'+temp2+'" id="'+temp2+'" value="'+settingsObj[temp][temp2]+'"></div>');
					}
					$('#'+temp).append('<button data-inline="true" data-theme="g" class="saveChanges">Save Changes</button>');
				}
				$('#tabsul').html(ulVals);
			}
		});
 
 $('#uploadfile').on('submit', function(e)
	{
		e.stopPropagation(); // Stop stuff happening
		e.preventDefault(); // Totally stop stuff happening
	$('progress').css({visibility: 'visible'});
	
    var formData = new FormData($(this)[0]);
    $.ajax({
        url: '/upload',  //Server script to process data
        type: 'POST',
		data: formData,
        xhr: function() {  // Custom XMLHttpRequest
            var myXhr = $.ajaxSettings.xhr();
            if(myXhr.upload){ // Check if upload property exists
                myXhr.upload.addEventListener('progress',progressHandlingFunction, false); // For handling the progress of the upload
            }
            return myXhr;
        },
        success: function(){
			$('#uploadfile')[0].reset();
			$('progress').css({visibility: 'hidden'});
			$('progress').attr({value:0,max:100});
		},
        error: function(jqXHR, textStatus, errorThrown)
		{
			alert('ERRORS: ' + textStatus);
		},
        cache: false,
        contentType: false,
        processData: false
    });
});

function progressHandlingFunction(e){
    if(e.lengthComputable){
        $('progress').attr({value:e.loaded,max:e.total});
    }
}
	// Add events
	//$('input[type=file]').on('change', function (event)
	//{
		//files = event.target.files;
	//});
	/*$('#uploadfile').on('submit', function(event)
	{
		event.stopPropagation(); // Stop stuff happening
		event.preventDefault(); // Totally stop stuff happening

		// Create a formdata object and add the files
		var data = new FormData();
		$.each(files, function(key, value)
		{
			data.append('myfile', value);
		});

		$.ajax({
			url: '/upload',
			type: 'POST',
			data: data,
			cache: false,
			dataType: 'text',
			processData: false, // Don't process the files
			contentType: false, // Set content type to false as jQuery will tell the server its a query string request
			success: function(data, textStatus, jqXHR)
			{
				if(typeof data.error === 'undefined')
				{
					// Success so call function to process the form
					submitForm(event, data);
				}
				else
				{
					// Handle errors here
					console.log('ERRORS: ' + data.error);
				}
			},
			error: function(jqXHR, textStatus, errorThrown)
			{
				// Handle errors here
				console.log('ERRORS: ' + textStatus);
				// STOP LOADING SPINNER
			}
		});
	});*/
	
	$('#tabs').on('click','.saveChanges',function(){
		var config = {};
		for(obj in settingsObj){
		config[obj]={};
		$('#'+obj+' input').serializeArray().map(function(item) {
			config[obj][item.name] = item.value;
			});
		}
		$.ajax({
			type: 'POST',
			url: '/ajax',
			async: true,
			data: 'option=6&object='+JSON.stringify(config),
			success: function(data)
			{
			}
			});
	});
	
	$('.song').click(function(){
		selectedsong=this.id;
		$('#popupTitle').html($(this).html());
		$("#popupSong").popup('open');
	});
	
	$('#playNow').click(function()
	{
		$("#popupSong").popup('close');
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=1&song='+selectedsong,
			async: true
		});
	});
	
	$('#playlistsul').on('click','.playlist',function(){
		selectedsong=this.id;
		$('#popupTitlelist').html($(this).html());
		$("#popupPlaylist").popup('open');
	});
	
	$('#playNowlist').click(function()
	{
		$("#popupPlaylist").popup('close');
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=0&playlist='+selectedsong,
			async: true
		});
	});
	$('#playNowlist_SMS').click(function()
	{
		$("#popupPlaylist").popup('close');
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=1&playlist='+selectedsong,
			async: true
		});
	});
	
	$('#deletelist').click(function()
	{
		var a=confirm('Are you sure you want to delete this playlist');
		if(a){
			$("#popupPlaylist").popup('close');
			$.ajax({
				type: 'POST',
				url: '/ajax',
				data: 'option=10&playlist='+selectedsong,
				dataType:'json',
				async: true,
				success:function(data){
					refreshPlaylistUL(data);
				}
			});			
		}
	});

	$('#addToQueue').click(function()
	{
		$("#popupSong").popup('close');
		$.ajax({
			type: 'POST',
			url: '/ajax.php',
			data: 'option=5&song='+selectedsong,
			async: true
		});
	});
	
	$('#lightsOn').click(function()
	{
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=3',
			async: true,
			success: function(data)
			{

			}
		});
	});
	
	$('#lightsOff').click(function()
	{
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=4',
			async: true,
			success: function(data)
			{

			}
		});
	});	
	
	$('#playallmusic').click(function()
	{
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=7',
			async: true,
			success: function(data)
			{

			}
		});
	});
	
	$("#playlistsongs").on('click','.songsforplaylist',function()
	{
		if($(this).hasClass('ui-btn-d')){
			$(this).removeClass("ui-btn-d").addClass("ui-btn-e");
		}
		else{
			$(this).removeClass("ui-btn-e").addClass("ui-btn-d");
		}
	});
	
	$('#newplaylistsubmit').click(function(){
		var name=$("#newplaylistname").val();
		if(name==''){
			alert('Please Enter a name');
			return false;
		}
		var temp='';
		$('.songsforplaylist.ui-btn-e').each(function(){
			temp+=$(this).html().replace(/\.[^/.]+$/, "")+"\t"+$(this).data('filename')+"\r\n";
		});
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=9&val='+temp+'&name='+name,
			async: true,
			dataType:'json',
			success: function(data)
			{
				refreshPlaylistUL(data);
			}
		});		
	});
	
	$('#newplaylist').click(function(){
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=8',
			dataType:'json',
			async: true,
			success: function(data)
			{
				var temp='';
				for(var i=0;i<data.songs.length;i++){
					temp+="<li data-theme='d'><a class='songsforplaylist' href='#' data-filename=\""+data.songs[i][1]+"\">"+data.songs[i][0]+"</a></li>";
				}
				$('#playlistsongs').html(temp);
				try{$('#playlistsongs').listview('refresh');}catch(e){$('#playlistsongs').listview();}
				$('#popupNewPlaylist').popup('open');
			}
		});
	});
});
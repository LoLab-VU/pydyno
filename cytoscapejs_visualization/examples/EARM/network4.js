/**
 * Created by dionisio on 2/22/17.
 */
fetch('data.json', {mode: 'no-cors'})
  .then(function(res) {
	return res.json()
  })
  .then(function(data) {
		var cy = window.cy = cytoscape({
		container: document.getElementById('cy'),
		boxSelectionEnabled: false,
		autounselectify: true,

		layout: {
			name: 'preset'
		},

		style: cytoscape.stylesheet()
			.selector('node')
			.css({
				'label': 'data(label)',
				'pie-size': '80%',
				'pie-1-background-color': 'data(background_color)',
				'pie-1-background-size': '100',
				'pie-2-background-color': '#dddcd4',
				'pie-2-background-size': '100',
			})

			.selector('edge')
			.css({
				'curve-style': 'bezier',
				// 'width': 'data(width)',
				'target-arrow-shape': 'data(target_arrow_shape)',
				'source-arrow-shape': 'data(source_arrow_shape)',
			}),

		elements: data.elements
		});



		// console.log(`data(edge_size_t${t})`)
	// for (let t = 0; t < 99; t++) {
	//     cy.batch(function () {
	//         cy.edges().forEach(function (n) {
	//             var c = n.data(`edge_color_t${t}`);
	//             n.style({'line-color': c})
	//
	//         })
	//     });
	//     console.log(cy.edges()[0].style())
	//
	// }

	  cy.elements().qtip({
		  content: ' ',
		  position: {
			  my: 'bottom right',
			  at: 'bottom left'
		  },
		  style: {
			  classes: 'qtip-bootstrap',
			  tip: {
				  width: 8,
				  height: 4
			  }
		  }
	  });
	  var tspan = data.data.tspan;
	  var text = document.getElementById('textInput');
	  var rangeInput = document.getElementById("range");
	  rangeInput.max = tspan.length;
      document.getElementById('myHeader').innerHTML = data.data.name;


	  function update_nodes(t){
	      rangeInput.value = t;
		  text.value = tspan[t].toFixed(2);
		  cy.batch(function(){
		  cy.edges().forEach(function (e) {
			  var c = e.data(`edge_color_t${t}`);
			  var s = e.data(`edge_size_t${t}`);
			  var a = e.data(`edge_qtip_t${t}`);
			  e.style({'line-color': c,
				  'target-arrow-color': c,
				  'source-arrow-color': c,
				  'width': s});

			  // e.animate({
			  //     style: {'line-color': c,
			  //         'target-arrow-color': c,
			  //         'source-arrow-color': c,
			  //         'width': s},
			  //     duration: 100,
			  //     queue: false
			  // });
			  e.qtip('api').set('content.text', a.toString());
	// n.animate({style: {'width': s}})

		  });
		  cy.nodes().forEach(function(n){
			  var p = n.data(`rel_value_t${t}`);
			  var q = n.data(`abs_value_t${t}`);
			  n.style({'pie-1-background-size': p});

			  // n.animate({
			  //     style: {'pie-1-background-size': p},
			  //     duration: 100,
			  //     queue: false
			  // });
			  n.qtip('api').set('content.text', q.toString())
		  });
	  })
	  }

	  var currentTime = 0;
	  var tInterval = null;

	  function nextTime(){
		  currentTime = currentTime+1;
		  if (currentTime >= tspan.length){
			  clearInterval(tInterval)
		  }
		  else {update_nodes(currentTime)}
	  }

	  var playing = false;
	  var playButton = document.getElementById('Play');

	  function pauseSlideshow(){
		  playButton.innerHTML = 'Play';
		  playing = false;
		  clearInterval(tInterval);
	  }

	  function playSlideshow(){
		  playButton.innerHTML = 'Pause';
		  playing = true;
		  tInterval = setInterval(nextTime, 1000)
	  }

	  // var advanceTime = function(){
	  //     if (t < tspan.length){
	  //         update_nodes(t);
	  //         t ++;
	  //         setTimeout(advanceTime, 1)
	  //     }
	  // };

	// function advanceByButton() {
	//     startT += 1;
	//     console.log(startT)
	//     update_nodes(startT)
	// }
	  var resetButton = document.getElementById('Reset');
	  resetButton.onclick = function(){
		  pauseSlideshow();
		  currentTime = 0;
		  update_nodes(currentTime)
	  };

	  playButton.onclick = function(){
		  if(playing){ pauseSlideshow(); }
		  else{ playSlideshow(); }

      rangeInput.addEventListener('mouseup', function(){
          pauseSlideshow();
          currentTime = this.value;
          currentTime = parseInt(currentTime)
          update_nodes(currentTime);

      });

      rangeInput.onchange = function(){
		      text.value = tspan[this.value].toFixed(2);
		      // currentTime = this.value
      }
};

	  // var advanceButton = document.getElementById('Play');
	  // advanceButton.addEventListener('click', function () {
	  //     nextTime()
	  // });


	// update_nodes(startT)
  }); // on dom ready
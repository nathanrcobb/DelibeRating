﻿$(document).ready(function () {
    var options = [];

    $('.dmenu a').on('click', function (event) {
        event.stopPropagation();
        event.preventDefault();
    });

    $('.chk a').on('click', function () {
        var $checkbox = $(this).find(':checkbox');

        $checkbox.attr('checked', !$checkbox.attr('checked'));
        event.stopPropagation();
        event.preventDefault();
    });

    $('.rdo a').on("click", function (event) {
        var $radio_button = $(this).find(':radio');

        if (($radio_button).attr('class') === 'rdobtn1') {
            $('input[class="rdobtn1"]').prop('checked', false);
        } else {
            $('input[class="rdobtn2"]').prop('checked', false);
        }
        $radio_button.prop("checked", true);
        event.stopPropagation();
        event.preventDefault();

    });

    $('button[id="rndmbtn"]').on("click", function (event) {
        ($('form[id="search"]')).attr('action', 'random/');
    });

    $('#search').submit(function (event) {
        var $q = ($('input[name="q"]'));
        var $loc = ($('input[name="loc"]'));
        var $rad = ($('input[name="rad"]'));
        var $sort = ($('input[name="sort"]'));
        var $price = ($('input[name="price"]'));
        var $open = ($('input[name="open"]'));

        var query = String(($('input[id="q"]').val())) ? String(($('input[id="q"]').val())) : 'food';
        var location = String(($('input[id="loc"]').val())) ? String(($('input[id="loc"]').val())) : 'Irvine, CA';
        var radius = ($('input[class="rdobtn1"]:checked').is(':checked')) ? ($('input[class="rdobtn1"]:checked').attr('data-value')) : 8050;
        var sortby = ($('input[class="rdobtn2"]:checked').is(':checked')) ? ($('input[class="rdobtn2"]:checked').attr('data-value')) : 'best_match';
        var price = [];
        var opennow = ($('input[id="opennow"]').attr('checked')) ? true : false;

        event.preventDefault();

        if ($('#price1').is(':checked')) {
            price.push('1');
        }
        if ($('#price2').is(':checked')) {
            price.push('2');
        }
        if ($('#price3').is(':checked')) {
            price.push('3');
        }
        if ($('#price4').is(':checked')) {
            price.push('4');
        }
        if (price.length === 0) {
            price = ['1', '2', '3', '4']
        }

        $q.attr('value', String(query));
        $loc.attr('value', String(location));
        $rad.attr('value', String(radius));
        $sort.attr('value', String(sortby));
        $price.attr('value', String(price));
        $open.attr('value', String(opennow));

        ($('form[id="search"]')).off('submit').submit();
    });

    $('.grp-add').on("click", function (event) {
        var $parli = $(event.target).parent();
        var $act = $parli.find($('input[name="act"]'));
        var $grp = $parli.find($('input[name="grp"]'));
        
        $act.attr('value', $parli.find('input[name="aa"]').attr('value'));
        $grp.attr('value', $parli.find('input[name="ga"]').attr('value'));
    });

    $('#vote-add').on("click", function (event) {
        var $parform = $(event.target).parent();
        var $grp = $parform.find($('input[name="grp"]'));
        
        $grp.attr('value', $parform.find('input[name="g"]').attr('value'));
    });
        
    $('input[name="q"]').autocomplete({
        source: "api/search/",
        minLength: 2,
        delay: 250,
        open: function () {
            setTimeout(function () {
                $('.ui-autocomplete').css('z-index', 99);
            }, 0);
        },
    });

    $('input[name="usr"]').autocomplete({
        source: "api/users/",
        minLength: 2,
        delay: 250,
        open: function () {
            setTimeout(function () {
                $('.ui-autocomplete').css('z-index', 99);
            }, 0);
        },
    });

    $('.vote-opt').click(function () {
        $.ajax({
            type: "POST",
            url: "/api/addopt",
            data: JSON.stringify({
                'vote_name': $(this).attr('value'),
                'element_id': $(this).attr('id'),
            }),
            dataType: "json",
            success: function (response) {
                /* Update state (button) */
            },
            error: function (rs, e) {
                /* Error condition */
            }
        });
    });

    $('.upvote').click(function () {
        $.ajax({
            type: "POST",
            url: "/api/upvote",
            data: JSON.stringify({
                'vote_name': $(this).attr('value'),
                'element_id': $(this).attr('id')
            }),
            dataType: "json",
            success: function (response) {
                if (response.success === true) {
                    $(response.element_id).attr('class', 'btn btn-default upvote');
                } else {
                    $(response.element_id).attr('class', 'btn btn-success upvote');
                }
                if(response.toggled === true) {
                    $(response.element_id).attr('class', 'btn btn-danger upvote');
                }
            },
            error: function (rs, e) {
                alert(e);
            }
        });
    });

    $('.downvote').click(function () {
        $.ajax({
            type: "POST",
            url: "/api/downvote",
            data: JSON.stringify({
                'vote_name': $(this).attr('value'),
                'element_id': $(this).attr('id')
            }),
            dataType: "json",
            success: function (response) {
                if (response.success === true) {
                    $(response.element_id).attr('class', 'btn btn-default downvote');
                } else {
                    $(response.element_id).attr('class', 'btn btn-danger downvote');
                }
                if (response.toggled === true) {
                    $(response.element_id).attr('class', 'btn btn-success upvote');
                }
            },
            error: function (rs, e) {
                alert(e);
            }
        });
    });
});
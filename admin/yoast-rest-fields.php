<?php
/**
 * Plugin Name: Yoast SEO REST API Fields
 * Description: Registers Yoast SEO meta fields as writable via the WordPress REST API.
 *              Drop this file into wp-content/mu-plugins/ on your WordPress site.
 * Version: 1.0
 */

add_action('rest_api_init', function () {

    $yoast_fields = [
        '_yoast_wpseo_title'                  => 'string',
        '_yoast_wpseo_metadesc'               => 'string',
        '_yoast_wpseo_focuskw'                => 'string',
        '_yoast_wpseo_canonical'              => 'string',
        '_yoast_wpseo_opengraph-title'        => 'string',
        '_yoast_wpseo_opengraph-description'  => 'string',
        '_yoast_wpseo_opengraph-image'        => 'string',
        '_yoast_wpseo_twitter-title'          => 'string',
        '_yoast_wpseo_twitter-description'    => 'string',
    ];

    foreach ($yoast_fields as $field => $type) {
        register_post_meta('post', $field, [
            'show_in_rest'  => true,
            'single'        => true,
            'type'          => $type,
            'auth_callback' => function () {
                return current_user_can('edit_posts');
            },
        ]);
    }
});

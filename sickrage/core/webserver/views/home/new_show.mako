<%inherit file="../layouts/main.mako"/>
<%!
    import sickrage
    from sickrage.core.helpers import anon_url
    from sickrage.indexers import IndexerApi
%>

<%block name="metas">
    <meta data-var="sickrage.DEFAULT_LANGUAGE" data-content="${sickrage.app.config.indexer_default_language}">
    <meta data-var="sickrage.LANGUAGES" data-content="${','.join(IndexerApi().indexer().languages.keys())}">
</%block>

<%block name="content">
    <div class="row">
        <div class="col-lg-10 mx-auto">
            <div class="sickrage-stepper mb-3">
                <div class="stepwizard">
                    <div class="stepwizard-row setup-panel form-inline">
                        <div class="stepwizard-step col-auto">
                            <a href="#step-1" class="btn btn-success btn-circle">1</a>
                            <p>
                                <small class="text-white">${_('Find A Show')}</small>
                            </p>
                        </div>
                        <div class="stepwizard-step col-auto">
                            <a href="#step-2" class="btn btn-dark btn-circle disabled">2</a>
                            <p>
                                <small class="text-white">${_('Pick A Folder')}</small>
                            </p>
                        </div>
                        <div class="stepwizard-step col-auto">
                            <a href="#step-3" class="btn btn-dark btn-circle disabled">3</a>
                            <p>
                                <small class="text-white">${_('Custom Options')}</small>
                            </p>
                        </div>
                    </div>
                </div>

                <form class="needs-validation" id="addShowForm" method="post"
                      action="${srWebRoot}/home/addShows/addNewShow">
                    <div class="card setup-content active" id="step-1">
                        <div class="card-header">
                            <h3 class="card-title">${_('Find a show')}</h3>
                        </div>
                        <div class="card-body">
                            <div class="form-group">
                                <input type="hidden" id="indexer_timeout"
                                       value="${sickrage.app.config.indexer_timeout}"/>
                                % if use_provided_info:
                                ${_('Show retrieved from existing metadata:')}
                                    <a href="${anon_url(IndexerApi(provided_indexer).config['show_url'], provided_indexer_id)}">
                                        ${provided_indexer_name}
                                    </a>
                                    <input type="hidden" id="indexerLang" name="indexerLang"
                                           value="${sickrage.app.config.indexer_default_language}"/>
                                    <input type="hidden" id="whichSeries" name="whichSeries"
                                           value="${provided_indexer_id}"/>
                                    <input type="hidden" id="providedIndexer" name="providedIndexer"
                                           value="${provided_indexer}"/>
                                    <input type="hidden" id="providedName"
                                           value="${provided_indexer_name}"/>
                                % else:
                                    <div class="row">
                                        <div class="col-md-12">
                                            <div class="input-group">
                                                <div class="input-group-prepend">
                                                    <span class="input-group-text">
                                                        <span class="fas fa-tv"></span>
                                                    </span>
                                                </div>
                                                <input id="nameToSearch" value="${default_show_name}"
                                                       title="TV show name" class="form-control" required/>
                                                <select name="providedIndexer" id="providedIndexer"
                                                        class="form-control" title="Choose indexer">
                                                    % for indexer in indexers:
                                                        <option value="${indexer}" ${('', 'selected')[provided_indexer == indexer]}>
                                                            ${indexers[indexer]}
                                                        </option>
                                                    % endfor
                                                </select>
                                                <div class="invalid-feedback">
                                                    ${_('Please choose a show')}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <br/>
                                    <div class="row">
                                        <div class="col-md-12">
                                            <div class="input-group">
                                                <div class="input-group-prepend">
                                                    <span class="input-group-text">
                                                        <span class="fas fa-flag"></span>
                                                    </span>
                                                </div>
                                                <select name="indexerLang" id="indexerLang" class="form-control"
                                                        title="${_('Choose language')}">
                                                    % for language in IndexerApi().indexer().languages.keys():
                                                        <option value="${language}" ${('', 'selected')[sickrage.app.config.indexer_default_language == language]}>
                                                            ${sickrage.subtitles.name_from_code(language)}
                                                        </option>
                                                    % endfor
                                                </select>
                                            </div>
                                        </div>
                                    </div>
                                    <p>
                                    <div id="messages"></div>
                                % endif
                            </div>
                        </div>
                        <div class="card-footer">
                            <button class="btn btn-success btn-inline" type="button" id="searchName">
                                ${_('Search')}
                            </button>
                            <button class="btn btn-primary nextBtn disabled pull-right" type="button">
                                ${_('Next')}
                            </button>
                        </div>
                    </div>

                    <div class="card setup-content" id="step-2">
                        <div class="card-header">
                            <h3 class="card-title">${_('Pick a folder')}</h3>
                        </div>
                        <div class="card-body">
                            <div class="form-group">
                                % if provided_show_dir:
                                ${_('Pre-chosen Destination Folder:')}
                                    <b>${provided_show_dir}</b><br/>
                                    <input type="hidden" id="fullShowPath" name="fullShowPath"
                                           value="${provided_show_dir}"/><br>
                                % else:
                                    <%include file="../includes/root_dirs.mako"/>
                                % endif
                            </div>
                        </div>
                        <div class="card-footer">
                            <button class="btn btn-primary nextBtn pull-right" type="button">
                                ${_('Next')}
                            </button>
                        </div>
                    </div>

                    <div class="card setup-content" id="step-3">
                        <div class="card-header">
                            <h3 class="card-title">${_('Custom options')}</h3>
                        </div>
                        <div class="card-body">
                            <div class="form-group">
                                    <%include file="../includes/add_show_options.mako"/>
                            </div>
                        </div>
                        <div class="card-footer">
                            <button class="btn btn-success pull-right" type="submit">
                                ${_('Finish!')}
                            </button>
                        </div>
                    </div>

                    % for curNextDir in other_shows:
                        <input type="hidden" name="other_shows" value="${curNextDir}"/>
                    % endfor
                    <input type="hidden" name="skipShow" id="skipShow" value=""/>
                </form>
                <div style="width: 100%; text-align: center;">
                    % if provided_show_dir:
                        <input class="btn" type="button" id="skipShowButton" value="${_('Skip Show')}"/>
                    % endif
                </div>
            </div>
        </div>
    </div>
</%block>
